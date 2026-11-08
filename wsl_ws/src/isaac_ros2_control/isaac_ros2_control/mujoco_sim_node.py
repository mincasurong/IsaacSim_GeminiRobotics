from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from rclpy.parameter import Parameter
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty
from tf2_msgs.msg import TFMessage

for _cand in (
    Path(__file__).resolve().parent,
    Path(__file__).resolve().parents[4],
    Path.home() / "mujoco_ws",
    Path.home() / "catkin_ws" / "src" / "isaac_ros2_control" / "isaac_ros2_control",
):
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

try:
    from isaac_ros2_control.mujoco_env import StampMuJoCoEnv  # noqa: E402
except ImportError:
    from mujoco_env import StampMuJoCoEnv  # noqa: E402

try:
    from isaac_ros2_control import kinematics
except ImportError:
    import kinematics


class MuJoCoWorkcellNode(Node):
    def __init__(
        self,
        workcell_mode: Optional[int] = None,
        enable_viewer: Optional[bool] = None,
    ) -> None:
        super().__init__("mujoco_sim_node")
        self.declare_parameter("workcell_mode", 3 if workcell_mode is None else int(workcell_mode))
        self.declare_parameter("enable_viewer", False if enable_viewer is None else bool(enable_viewer))

        resolved_mode = (
            int(workcell_mode)
            if workcell_mode is not None
            else int(self.get_parameter("workcell_mode").value)
        )
        resolved_viewer = (
            bool(enable_viewer)
            if enable_viewer is not None
            else bool(self.get_parameter("enable_viewer").value)
        )

        self.clock_pub = self.create_publisher(Clock, "/clock", 10)
        self.tf_pub = self.create_publisher(TFMessage, "/tf", 20)
        self.js_pubs: Dict[str, Any] = {}
        self.cmd_subs: Dict[str, Any] = {}
        self.latest_cmds: Dict[str, List[float]] = {}
        self._viewer = None

        self.configure_mode(resolved_mode, enable_viewer=resolved_viewer)
        self.reset_sub = self.create_subscription(Empty, "/reset_simulation", self._reset_cb, 10)
        self.timer = self.create_timer(0.02, self._step_and_publish_50hz)
        self.get_logger().info(
            f"WSL2 Native MuJoCo Workcell Node started (Mode {self.workcell_mode}, "
            f"arms={list(self.env.bases.keys())}, 250Hz physics / 50Hz ROS 2)."
        )

    def configure_mode(self, mode: int, enable_viewer: bool = False) -> None:
        self.workcell_mode = int(mode)
        self.enable_viewer = bool(enable_viewer)
        self.env = StampMuJoCoEnv(mode=self.workcell_mode, render_obs=False)
        self.obs = self.env.reset()

        for arm_id in ("FR3_1", "FR3_2", "FR3_3"):
            prefix = arm_id.lower()
            if arm_id not in self.js_pubs:
                self.js_pubs[arm_id] = self.create_publisher(JointState, f"/{prefix}/joint_states", 10)
            if arm_id not in self.cmd_subs:
                self.cmd_subs[arm_id] = self.create_subscription(
                    JointState,
                    f"/{prefix}/joint_commands",
                    lambda msg, a=arm_id: self._joint_cmd_cb(msg, a),
                    10,
                )
            self.latest_cmds[arm_id] = list(kinematics.FR3_HOME_CONFIG) + [0.04]

        if self.enable_viewer and self._viewer is None:
            try:
                import mujoco.viewer

                self._viewer = mujoco.viewer.launch_passive(self.env.model, self.env.data)
            except Exception as exc:
                self.get_logger().warn(f"Headless WSL2 mode (passive viewer not opened): {exc}")

    def _joint_cmd_cb(self, msg: JointState, arm_id: str) -> None:
        if len(msg.position) >= 7:
            cmd = [float(x) for x in msg.position[:7]]
            grip = float(msg.position[7]) if len(msg.position) >= 8 else 0.04
            self.latest_cmds[arm_id] = cmd + [grip]

    def _reset_cb(self, _msg: Empty) -> None:
        self.obs = self.env.reset()
        for arm_id in ("FR3_1", "FR3_2", "FR3_3"):
            self.latest_cmds[arm_id] = list(kinematics.FR3_HOME_CONFIG) + [0.04]
        self.get_logger().info("Reset MuJoCo workcell state.")

    def _step_and_publish_50hz(self) -> None:
        active_cmds = {
            arm_id: self.latest_cmds.get(arm_id, list(kinematics.FR3_HOME_CONFIG) + [0.04])
            for arm_id in self.env.bases
        }
        self.obs = self.env.step(active_cmds, substeps=5)
        if self._viewer is not None and self._viewer.is_running():
            self._viewer.sync()

        sim_t = float(self.env.data.time)
        sec = int(sim_t)
        nanosec = int((sim_t - sec) * 1e9)

        clk = Clock()
        clk.clock.sec = sec
        clk.clock.nanosec = nanosec
        if not rclpy.ok():
            return
        self.clock_pub.publish(clk)

        stamp_msg = clk.clock
        tf_list: List[TransformStamped] = []

        for arm_id, r_obs in self.obs["robots"].items():
            prefix = arm_id.lower()
            arm_num = prefix.split("_")[-1]
            grip_val = float(r_obs.get("gripper_pos", 0.04))

            js = JointState()
            js.header.stamp = stamp_msg
            js.name = [f"fr3_joint{i}" for i in range(1, 8)] + ["fr3_finger_joint1", "fr3_finger_joint2"]
            js.position = list(r_obs["joint_pos"]) + [grip_val, grip_val]
            self.js_pubs[arm_id].publish(js)

            b_xyz, b_yaw = self.env.get_arm_base(arm_id)
            base_frame_aliases = [
                f"{arm_id}_fr3_link0",
                f"{prefix}_fr3_link0",
                f"{prefix}_link0",
                f"robot{arm_num}_fr3_link0",
            ]
            if arm_id == "FR3_1":
                base_frame_aliases.append("fr3_link0")

            for b_frame in base_frame_aliases:
                t_base = TransformStamped()
                t_base.header.stamp = stamp_msg
                t_base.header.frame_id = "world"
                t_base.child_frame_id = b_frame
                t_base.transform.translation.x = float(b_xyz[0])
                t_base.transform.translation.y = float(b_xyz[1])
                t_base.transform.translation.z = float(b_xyz[2])
                t_base.transform.rotation.w = float(math.cos(b_yaw / 2.0))
                t_base.transform.rotation.z = float(math.sin(b_yaw / 2.0))
                tf_list.append(t_base)

        for obj_name, obj_data in self.obs["objects"].items():
            ox, oy, oz = obj_data["pos"]
            qw, qx, qy, qz = obj_data["quat_wxyz"]
            t_w = TransformStamped()
            t_w.header.stamp = stamp_msg
            t_w.header.frame_id = "world"
            t_w.child_frame_id = obj_name
            t_w.transform.translation.x = float(ox)
            t_w.transform.translation.y = float(oy)
            t_w.transform.translation.z = float(oz)
            t_w.transform.rotation.w = float(qw)
            t_w.transform.rotation.x = float(qx)
            t_w.transform.rotation.y = float(qy)
            t_w.transform.rotation.z = float(qz)
            tf_list.append(t_w)

        tf_msg = TFMessage(transforms=tf_list)
        self.tf_pub.publish(tf_msg)


def main(args: Optional[List[str]] = None) -> None:
    rclpy.init(args=args)
    node = MuJoCoWorkcellNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

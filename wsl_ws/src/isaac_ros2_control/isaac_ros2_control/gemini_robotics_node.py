"""ROS 2 node integrating Gemini-4-Argon for vision-driven
pick-and-place orchestration using Function Calling.

Subscribes to:
    /overhead_camera/rgb         (sensor_msgs/Image)
    /overhead_camera/depth       (sensor_msgs/Image)
    /overhead_camera/camera_info (sensor_msgs/CameraInfo)
    /gemini/action_result        (std_msgs/String)  <- Results from controller

Publishes:
    /gemini/detected_objects     (std_msgs/String)  -> JSON detections
    /gemini/action               (std_msgs/String)  -> JSON action command

Services:
    /gemini/detect_objects       (std_srvs/Trigger) <- trigger detection
    /gemini/plan_task            (std_srvs/Trigger) <- trigger planning (agentic loop)
    /gemini/describe_scene       (std_srvs/Trigger) <- describe scene
"""

import concurrent.futures
import json
import time
import traceback
import uuid
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String, Empty
from std_srvs.srv import Trigger
import tf2_ros

try:
    from cv_bridge import CvBridge
except ImportError:
    CvBridge = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

try:
    from isaac_ros2_control import gemini_config
    from isaac_ros2_control import gemini_utils
    from isaac_ros2_control import gemini_prompts
    from isaac_ros2_control import gemini_tools
    from isaac_ros2_control import workspace_state
    from isaac_ros2_control.rule_based_verifier import (
        RuleBasedTaskGenerator,
        RuleBasedTaskVerifier,
    )
except ImportError:
    try:
        from . import gemini_config
        from . import gemini_utils
        from . import gemini_prompts
        from . import gemini_tools
        from . import workspace_state
        from .rule_based_verifier import (
            RuleBasedTaskGenerator,
            RuleBasedTaskVerifier,
        )
    except ImportError:
        import gemini_config
        import gemini_utils
        import gemini_prompts
        import gemini_tools
        import workspace_state
        from rule_based_verifier import (
            RuleBasedTaskGenerator,
            RuleBasedTaskVerifier,
        )

try:
    from isaac_ros2_control import model_comparator
except ImportError:
    try:
        from . import model_comparator
    except ImportError:
        import model_comparator

try:
    from isaac_ros2_control import experiment_logger
except ImportError:
    try:
        import experiment_logger
    except ImportError:
        experiment_logger = None


class GeminiRoboticsNode(Node):
    """ROS 2 node that uses Gemini-4-Argon VLM for scene understanding
    and agentic task orchestration via Function Calling."""

    def __init__(self, node_name: str = 'gemini_robotics_node'):
        super().__init__(node_name)

        # Parameters
        self.declare_parameter('env_file', '')
        self.declare_parameter('detection_interval', 0.0)  # 0 = manual only

        env_file = self.get_parameter('env_file').get_parameter_value().string_value
        env_path = env_file if env_file else None

        # Gemini API Client
        if genai is None:
            self.get_logger().error(
                'google-genai package not installed. '
                'Install with: pip install google-genai'
            )
            self.client = None
        else:
            api_key = gemini_config.get_api_key(env_path)
            if not api_key:
                self.get_logger().error(
                    'No Gemini API key found. Set LLM_API_KEY in .env '
                    'or GEMINI_API_KEY environment variable.'
                )
                self.client = None
            else:
                self.client = genai.Client(api_key=api_key)
                self.get_logger().info('Gemini API client initialized.')

        self.model_name = gemini_config.get_model_name(env_path)
        self.fast_executor_model = gemini_config.get_planner_model(env_path)
        if self.fast_executor_model == self.model_name:
            self.fast_executor_model = "gemini-3.5-flash-lite" if self.model_name == "gemini-4-argon" else "gemini-4-argon"
        self.brain_mode = "argon_optimized"
        self.live_telemetry = {}
        self.completed_stage_rows = []
        self.active_trial_stats = None
        self._ignoring_self_reset = False
        self.get_logger().info(f'Using Brain model: {self.model_name} | Fast Executor: {self.fast_executor_model}')

        # CV Bridge
        if CvBridge is not None:
            self.bridge = CvBridge()
        else:
            self.bridge = None
            self.get_logger().warn('cv_bridge not available. Image conversion disabled.')

        # State
        self.latest_rgb = None
        self.latest_depth = None
        self.camera_intrinsics = None
        self.last_detections = None
        
        self.action_results = {}
        self.user_goal = "Your ultimate goal is to build a single, stable 9-layer tower on the central target table using ALL 9 available objects."
        self.is_running = False
        self.cancel_current_task = False
        
        # TF2 for querying block positions from Isaac Sim
        self.tf_buffer = tf2_ros.Buffer(node=self)
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Known robot base positions in world frame (from three_robot_tower.py)
        self.robot_bases = {
            'FR3_1': np.array([0.0, -0.45]),
            'FR3_2': np.array([0.3897, 0.225]),
            'FR3_3': np.array([-0.3897, 0.225]),
        }
        
        self.workspace_state = workspace_state.WorkspaceState()
        self.verifier = RuleBasedTaskVerifier(logger=self.get_logger())
        self.experiment_logger = None
        self.experiment_target_blocks = 9
        
    # Callback Groups
        from rclpy.callback_groups import ReentrantCallbackGroup
        self.cb_group = ReentrantCallbackGroup()

        # Subscribers
        self.rgb_sub = self.create_subscription(
            Image, '/overhead_camera/rgb', self._rgb_callback, 10, callback_group=self.cb_group)
        self.depth_sub = self.create_subscription(
            Image, '/overhead_camera/depth', self._depth_callback, 10, callback_group=self.cb_group)
        self.info_sub = self.create_subscription(
            CameraInfo, '/overhead_camera/camera_info', self._info_callback, 10, callback_group=self.cb_group)
            
        self.result_sub = self.create_subscription(
            String, '/gemini/action_result', self._result_callback, 10, callback_group=self.cb_group)
        self.custom_goal_sub = self.create_subscription(
            String, '/gemini/custom_goal', self._custom_goal_callback, 10, callback_group=self.cb_group)
        self.reset_sim_sub = self.create_subscription(
            Empty, '/reset_simulation', self._reset_sim_cb, 10, callback_group=self.cb_group)

        # Publishers
        self.detection_pub = self.create_publisher(
            String, '/gemini/detected_objects', 10)
        self.action_pub = self.create_publisher(
            String, '/gemini/action', 10)
        self.chat_pub = self.create_publisher(
            String, '/gemini/chat_reply', 10)
        self.comparison_pub = self.create_publisher(
            String, '/gemini/model_comparison', 10)
        self.reset_sim_pub = self.create_publisher(
            Empty, '/reset_simulation', 10)

        # Services
        self.detect_srv = self.create_service(
            Trigger, '/gemini/detect_objects', self._detect_objects_cb, callback_group=self.cb_group)
        self.plan_srv = self.create_service(
            Trigger, '/gemini/plan_task', self._plan_task_cb, callback_group=self.cb_group)
        self.describe_srv = self.create_service(
            Trigger, '/gemini/describe_scene', self._describe_scene_cb, callback_group=self.cb_group)

        # Optional periodic detection
        interval = self.get_parameter('detection_interval').get_parameter_value().double_value
        if interval > 0:
            self.create_timer(interval, self._periodic_detect, callback_group=self.cb_group)

        self.get_logger().info(
            'Gemini Robotics Node started (Function Calling mode). '
            'Call /gemini/plan_task to begin the agentic loop.'
        )

    # Camera Result Callbacks

    def _rgb_callback(self, msg):
        if self.bridge is not None:
            try:
                self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            except Exception as e:
                self.get_logger().warn(f'RGB conversion failed: {e}')

    def _depth_callback(self, msg):
        if self.bridge is not None:
            try:
                self.latest_depth = self.bridge.imgmsg_to_cv2(msg, 'passthrough')
            except Exception as e:
                self.get_logger().warn(f'Depth conversion failed: {e}')

    def _info_callback(self, msg):
        import numpy as np
        self.camera_intrinsics = np.array(msg.k).reshape(3, 3)

    def _result_callback(self, msg):
        try:
            res = json.loads(msg.data)
            raw_id = str(res.get("robot_id", "")).strip()
            if not raw_id or raw_id.lower() == "global":
                self.action_results["global"] = res
            else:
                norm_id = self._normalize_wait_key(raw_id)
                self.action_results[norm_id] = res
                self.action_results[raw_id] = res
        except Exception as e:
            self.get_logger().error(f"Failed to parse action result: {e}")

    @staticmethod
    def _normalize_wait_key(robot_id: str) -> str:
        s = str(robot_id or "").strip().upper()
        if not s or s == "GLOBAL" or "+" in s:
            return "global"
        if "1" in s:
            return "FR3_1"
        if "2" in s:
            return "FR3_2"
        if "3" in s:
            return "FR3_3"
        return s

    def _custom_goal_callback(self, msg):
        import time
        now = time.time()
        if hasattr(self, '_last_goal_time') and (now - self._last_goal_time < 2.0):
            self.get_logger().info("Ignoring duplicate goal command received within 2 seconds.")
            return
        self._last_goal_time = now
        
        try:
            payload = json.loads(msg.data)
            if isinstance(payload, dict) and "goal" in payload:
                self.user_goal = payload["goal"]
                if "brain_mode" in payload and payload["brain_mode"]:
                    self.brain_mode = str(payload["brain_mode"]).strip()
                sc_id = payload.get("scenario_id", "CUSTOM")
                trial_n = payload.get("trial_num", 1)
                self.experiment_target_blocks = payload.get("blocks_target", 9)
                if experiment_logger is not None:
                    self.experiment_logger = experiment_logger.ExperimentLogger(
                        scenario_id=sc_id,
                        trial_num=trial_n,
                        goal_text=self.user_goal,
                        model_name=self.model_name,
                        planner_model=gemini_config.get_planner_model()
                    )
            else:
                self.user_goal = msg.data
                self.experiment_target_blocks = 9
        except Exception:
            self.user_goal = msg.data
            self.experiment_target_blocks = 9

        self.get_logger().info(f"\033[92m[PROMPT] Received custom goal: {self.user_goal} (brain_mode={self.brain_mode})\033[0m")
        
        # Automatically trigger planning
        import threading
        def trigger_plan():
            from std_srvs.srv import Trigger
            req = Trigger.Request()
            res = Trigger.Response()
            self._plan_task_cb(req, res)
        
        threading.Thread(target=trigger_plan, daemon=True).start()

    def _reset_sim_cb(self, msg):
        if getattr(self, '_ignoring_self_reset', False):
            return
        self.get_logger().info("\033[93m[RESET] Resetting Rule-Based Task Verifier and workspace state.\033[0m")
        self.verifier.reset()
        self.action_results.clear()

    # Service Callbacks

    def _call_gemini(self, image_bytes, prompt, thinking_budget=0):
        """Call Gemini API with an image and a prompt."""
        if self.client is None:
            raise RuntimeError('Gemini API client is not initialized.')

        config_kwargs = {'temperature': 1.0}
        if thinking_budget > 0 and "flash-lite" not in str(self.model_name).lower():
            config_kwargs['thinking_config'] = genai_types.ThinkingConfig(
                thinking_budget=thinking_budget
            )

        t0 = time.monotonic()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                genai_types.Part.from_bytes(
                    data=image_bytes, mime_type='image/png'),
                prompt,
            ],
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
        t_elapsed = time.monotonic() - t0
        if self.experiment_logger:
            self.experiment_logger.log_api_call(self.model_name, t_elapsed, success=True)
        return response.text

    # Service Handlers

    def _detect_objects_cb(self, request, response):
        """Service: detect objects in the latest camera frame."""
        if genai is None or self.client is None:
            response.success = False
            response.message = "google-genai client is not initialized. Run: pip install --break-system-packages google-genai"
            return response

        if self.latest_rgb is None:
            import time
            for _ in range(20):
                if self.latest_rgb is not None:
                    break
                time.sleep(0.1)

        if self.latest_rgb is None:
            response.success = False
            response.message = 'No camera frame available yet. Is Isaac Sim PLAYING?'
            return response

        try:
            result = self._fn_detect_objects()
            response.success = True
            response.message = f"Detected {len(result)} objects."
        except Exception as e:
            response.success = False
            response.message = f'Detection failed: {e}'
            self.get_logger().error(response.message)
        return response

    def _plan_task_cb(self, request, response):
        """Service: Trigger the agentic building loop."""
        if genai is None or genai_types is None or self.client is None:
            response.success = False
            response.message = (
                "google-genai is not initialized. Please install it in WSL2 with: "
                "'pip install --break-system-packages google-genai' and verify LLM_API_KEY in private/.env"
            )
            self.get_logger().error(response.message)
            return response

        if self.latest_rgb is None:
            # Wait briefly (up to 0.5s) for an optional camera frame; proceed with TF state if camera is disabled
            import time
            for _ in range(5):
                if self.latest_rgb is not None:
                    break
                time.sleep(0.1)

        if self.latest_rgb is None:
            self.get_logger().info(
                "[VLA] Overhead camera stream (/overhead_camera/rgb) not active; "
                "proceeding with real-time 3D TF workspace state."
            )

        if self.is_running:
            self.get_logger().warn("\033[93m[WARN] A task is already running. Cancelling it...\033[0m")
            self.cancel_current_task = True
            import time
            while self.is_running:
                time.sleep(0.1)
            self.cancel_current_task = False

        self.is_running = True
        self.verifier.reset()
        try:
            goal_norm = (self.user_goal or "").strip().lower()
            is_comp_cmd = (
                "start comparison test" in goal_norm
                or "comparison test" in goal_norm
                or "compare model" in goal_norm
                or self.brain_mode == "compare_ab"
            )
            if is_comp_cmd:
                self._run_automated_comparison_workflow()
            else:
                self._run_single_trial_and_report(self.brain_mode, self.user_goal)
            response.success = True
            response.message = "Agentic loop completed."
        except Exception as e:
            import traceback
            response.success = False
            response.message = f'Planning loop failed: {e}'
            self.get_logger().error(response.message)
            self.get_logger().error(traceback.format_exc())
        finally:
            self.is_running = False
            self.cancel_current_task = False
        return response

    def _describe_scene_cb(self, request, response):
        """Service: describe the current scene in natural language."""
        if genai is None or self.client is None:
            response.success = False
            response.message = "google-genai client is not initialized. Run: pip install --break-system-packages google-genai"
            return response
        if self.latest_rgb is None:
            import time
            for _ in range(20):
                if self.latest_rgb is not None:
                    break
                time.sleep(0.1)
                
        if self.latest_rgb is None:
            response.success = False
            response.message = 'No camera frame available yet. Is Isaac Sim PLAYING?'
            return response

        try:
            image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
            description = self._call_gemini(
                image_bytes, gemini_prompts.DESCRIBE_SCENE_PROMPT,
                thinking_budget=512)

            response.success = True
            response.message = description
            self.get_logger().info(f'Scene description: {description[:200]}...')
        except Exception as e:
            response.success = False
            response.message = f'Scene description failed: {e}'
        return response

    def _periodic_detect(self):
        """Timer callback for periodic automatic detection."""
        if self.latest_rgb is None or self.client is None:
            return
        try:
            self._fn_detect_objects()
        except Exception as e:
            self.get_logger().warn(f'Periodic detection failed: {e}')

    # Agentic Loop Tool Execution


    def _publish_chat(self, text: str, sender: str = "Comparison Orchestrator", emoji: str = "📊", role: str = "vla"):
        try:
            import uuid
            m = String()
            m.data = json.dumps({
                "id": str(uuid.uuid4()),
                "text": text,
                "senderName": sender,
                "emoji": emoji,
                "role": role,
            })
            self.chat_pub.publish(m)
        except Exception:
            pass

    def _new_trial_accumulator(self, stage_id: str, label: str, brain_model: str, exec_model: str) -> dict:
        return {
            "id": stage_id,
            "label": label,
            "brain_model": brain_model,
            "exec_model": exec_model,
            "plan_latency_ms": 0.0,
            "llm_time_ms": 0.0,
            "wall_time_s": 0.0,
            "turns": 0,
            "argon_calls": 0,
            "flash_lite_calls": 0,
            "er2_calls": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "thinking_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "tool_calls": 0,
            "verified_calls": 0,
            "blocks_placed": 0,
        }

    def _record_and_publish_telemetry(self, model_name: str, usage: dict, latency_ms: float, tool_calls: int = 0, verified_calls: int = 0, is_plan_step: bool = False):
        if self.active_trial_stats is not None:
            st = self.active_trial_stats
            if is_plan_step and st["plan_latency_ms"] == 0.0:
                st["plan_latency_ms"] = round(float(latency_ms), 1)
            st["llm_time_ms"] = round(st["llm_time_ms"] + float(latency_ms), 1)
            if not is_plan_step:
                st["turns"] += 1
            if "argon" in model_name:
                st["argon_calls"] += 1
            elif "flash" in model_name:
                st["flash_lite_calls"] += 1
            elif "robotics-er" in model_name:
                st["er2_calls"] += 1
            st["input_tokens"] += int(usage.get("input_tokens", 0))
            st["cached_tokens"] += int(usage.get("cached_tokens", 0))
            st["thinking_tokens"] += int(usage.get("thinking_tokens", 0))
            st["output_tokens"] += int(usage.get("output_tokens", 0))
            st["total_tokens"] += int(usage.get("total_tokens", 0))
            st["cost_usd"] = round(st["cost_usd"] + float(usage.get("cost_usd", 0.0)), 6)
            st["tool_calls"] += int(tool_calls)
            st["verified_calls"] += int(verified_calls)

    def _finalize_stage_row(self, st: dict) -> dict:
        pass_pct = round((st["verified_calls"] / st["tool_calls"]) * 100.0, 1) if st["tool_calls"] > 0 else 100.0
        return {
            "id": st["id"],
            "label": st["label"],
            "brain_model": st["brain_model"],
            "exec_model": st["exec_model"],
            "plan_latency_ms": st["plan_latency_ms"],
            "single_turn": {
                "input_tokens": st["input_tokens"],
                "cached_tokens": st["cached_tokens"],
                "thinking_tokens": st["thinking_tokens"],
                "output_tokens": st["output_tokens"],
                "total_tokens": st["total_tokens"],
                "cost_usd": st["cost_usd"],
            },
            "quality": {
                "tool_calls": st["tool_calls"],
                "verified_calls": st["verified_calls"],
                "pass_rate_pct": pass_pct,
                "blocks_placed": st["blocks_placed"],
            },
            "full_task_projection": {
                "turns": st["turns"],
                "argon_calls": st["argon_calls"],
                "flash_lite_calls": st["flash_lite_calls"],
                "er2_calls": st["er2_calls"],
                "total_tokens": st["total_tokens"],
                "cached_tokens": st["cached_tokens"],
                "thinking_tokens": st["thinking_tokens"],
                "cost_usd": st["cost_usd"],
                "est_wall_time_s": st["wall_time_s"],
                "savings_vs_pure_argon_pct": 0.0,
                "savings_vs_er2_pct": 0.0,
            },
        }

    def _recompute_savings_and_publish(self, status_text: str):
        er2_cost = next((r["full_task_projection"]["cost_usd"] for r in self.completed_stage_rows if r["id"] == "gemini-robotics-er-2-preview"), 0.0)
        argon_cost = next((r["full_task_projection"]["cost_usd"] for r in self.completed_stage_rows if r["id"] == "gemini-4-argon"), 0.0)
        for r in self.completed_stage_rows:
            c = r["full_task_projection"]["cost_usd"]
            r["full_task_projection"]["savings_vs_pure_argon_pct"] = round((1.0 - (c / argon_cost)) * 100.0, 1) if argon_cost > 0 else 0.0
            r["full_task_projection"]["savings_vs_er2_pct"] = round((1.0 - (c / er2_cost)) * 100.0, 1) if er2_cost > 0 else 0.0

        msg = String()
        msg.data = json.dumps({
            "timestamp": time.time(),
            "brain_mode": self.brain_mode,
            "status_text": status_text,
            "goal": self.user_goal,
            "comparison_rows": self.completed_stage_rows,
        })
        self.comparison_pub.publish(msg)

    def _run_single_trial_and_report(self, mode_id: str, goal_text: str) -> dict:
        import time
        labels = {
            "gemini-robotics-er-2-preview": ("gemini-robotics-er-2-preview", "Stage 1: Legacy Loop (Robotics-ER 2)", "gemini-robotics-er-2-preview", "gemini-robotics-er-2-preview"),
            "gemini-4-argon": ("gemini-4-argon", "Stage 2: Pure Gemini-4-Argon Loop", "gemini-4-argon", "gemini-4-argon"),
            "argon_optimized": ("argon_optimized", "Stage 3: Argon Brain (1x) + Flash-Lite", "gemini-4-argon", self.fast_executor_model),
        }
        sid, slabel, b_mod, e_mod = labels.get(mode_id, ("argon_optimized", f"Run ({mode_id})", self.model_name, self.fast_executor_model))
        self.brain_mode = mode_id
        self.user_goal = goal_text
        self.active_trial_stats = self._new_trial_accumulator(sid, slabel, b_mod, e_mod)
        t0 = time.monotonic()
        self._run_agentic_task()
        self.active_trial_stats["wall_time_s"] = round(time.monotonic() - t0, 2)
        row = self._finalize_stage_row(self.active_trial_stats)
        self.active_trial_stats = None

        replaced = False
        for idx, existing in enumerate(self.completed_stage_rows):
            if existing["id"] == sid:
                self.completed_stage_rows[idx] = row
                replaced = True
                break
        if not replaced:
            self.completed_stage_rows.append(row)

        is_dual = len(self.robot_bases) == 2
        target_cnt = 3 if is_dual else 9
        unit_label = "bar steps" if is_dual else "blocks"
        row["quality"]["target_count"] = target_cnt
        self._recompute_savings_and_publish(
            f"Completed {slabel}: {row['quality']['blocks_placed']}/{target_cnt} {unit_label}, {row['single_turn']['total_tokens']} tokens, ${row['single_turn']['cost_usd']:.5f}, {row['full_task_projection']['est_wall_time_s']}s"
        )
        return row

    def _trigger_full_reset_between_stages(self):
        import time
        self.get_logger().info("\033[93m[COMPARISON RESET] Resetting simulation and controller for next stage...\033[0m")
        self._ignoring_self_reset = True
        try:
            self.reset_sim_pub.publish(Empty())
        finally:
            self.verifier.reset()
            self.action_results.clear()
            time.sleep(4.0)
            self.workspace_state.update_from_tf(self.tf_buffer)
            self._ignoring_self_reset = False

    def _run_automated_comparison_workflow(self):
        is_dual = len(self.robot_bases) == 2
        if is_dual:
            self.experiment_target_blocks = 3
            bench_goal = (
                "Coordinate FR3_1 and FR3_2 to handle the blue LongBar in 3 steps: "
                "1) call dual_arm_pick(object_label='LongBar', offset_1=-0.25, offset_2=0.25, speed='fast'), "
                "2) call dual_arm_circle(radius=0.08, cycles=1, plane='XY', speed='fast'), "
                "3) call dual_arm_place(x=0.0, y=0.0, speed='fast')."
            )
            mode_title = "Modes 2 & 3 — Dual-Arm Blue LongBar Manipulation (Pick -> Circle -> Place)"
            unit_total = 3
            unit_name = "Bar Phases"
        else:
            self.experiment_target_blocks = 9
            bench_goal = "Build a 9-layer tower on the central target table using all 9 blocks (Block1..Block9) with maximum speed and concurrency."
            mode_title = "Mode 1 — 3-Arm 9-Block Tower"
            unit_total = 9
            unit_name = "Blocks Stacked"

        self.completed_stage_rows = []
        stages = [
            ("gemini-robotics-er-2-preview", "Stage 1/3: Legacy Loop (gemini-robotics-er-2-preview)"),
            ("gemini-4-argon", "Stage 2/3: Pure Gemini-4-Argon Loop (gemini-4-argon)"),
            ("argon_optimized", "Stage 3/3: Argon Brain (1x) + Flash-Lite Executor"),
        ]

        self._publish_chat(
            f"Starting Automated 3-Stage Comparison Test ({mode_title}):\n"
            "1) Execute task using Legacy Loop (`gemini-robotics-er-2-preview`) -> Generate Report -> Reset\n"
            "2) Execute task using `gemini-4-argon` only -> Generate Report -> Reset\n"
            "3) Execute task using `gemini-4-argon` Brain + `gemini-3.5-flash-lite` Executor -> Final Report."
        )

        for idx, (mode_id, stage_title) in enumerate(stages):
            if self.cancel_current_task:
                break
            self._recompute_savings_and_publish(f"Running {stage_title} ({mode_title})...")
            self._publish_chat(f"▶️ **{stage_title}** — executing {mode_title}...")
            row = self._run_single_trial_and_report(mode_id, bench_goal)
            st = row["single_turn"]
            q = row["quality"]
            fp = row["full_task_projection"]
            self._publish_chat(
                f"📋 **{stage_title} Report**:\n"
                f"- {unit_name}: `{q['blocks_placed']}/{unit_total}` | Verified Tool Calls: `{q['verified_calls']}/{q['tool_calls']}` (`{q['pass_rate_pct']}%`)\n"
                f"- Model Calls: `{fp['argon_calls']} Argon + {fp['flash_lite_calls']} Flash-Lite + {fp.get('er2_calls', 0)} ER-2` (`{fp['turns']}` turns)\n"
                f"- Tokens: `In={st['input_tokens']} (Cached={st['cached_tokens']}), Think={st['thinking_tokens']}, Out={st['output_tokens']}, Total={st['total_tokens']}`\n"
                f"- Wall Time: `{fp['est_wall_time_s']}s` | Stage Cost: **`${st['cost_usd']:.5f}`**"
            )
            if idx < len(stages) - 1 and not self.cancel_current_task:
                self._publish_chat("🔄 Resetting simulation and FR3 arms for next comparison stage...")
                self._trigger_full_reset_between_stages()

        self._recompute_savings_and_publish(f"Completed all 3 comparison stages ({mode_title}).")
        summary_lines = [f"🏁 **Final 3-Stage Comparison Summary ({mode_title})**:"]
        for r in self.completed_stage_rows:
            fp = r["full_task_projection"]
            q = r["quality"]
            summary_lines.append(
                f"- **{r['label']}**: `{q['blocks_placed']}/{unit_total}` | `{fp['total_tokens']}` tokens | `{fp['est_wall_time_s']}s` | **`${fp['cost_usd']:.5f}`** "
                f"(vs Pure Argon: `{fp['savings_vs_pure_argon_pct']:+.1f}%`, vs ER-2: `{fp['savings_vs_er2_pct']:+.1f}%`)"
            )
        self._publish_chat("\n".join(summary_lines))

    def _brainstorm_spatial_plan(self, goal_text: str, image_bytes: bytes = None) -> str:
        """Formulate high-level VLA plan using Rule-Based Task Generator + Gemini-4-Argon."""
        from google.genai import types as genai_types
        import time
        import uuid
        import json
        
        robotics_model = "gemini-robotics-er-2-preview" if self.brain_mode == "gemini-robotics-er-2-preview" else self.model_name
        
        def stream_chat(sender, emoji, role, model_name, req_contents, req_config):
            msg_id = str(uuid.uuid4())
            header = {
                "id": msg_id, 
                "text": "", 
                "senderName": f"{sender} ({model_name})", 
                "emoji": emoji, 
                "role": role
            }
            msg = String()
            msg.data = json.dumps(header)
            self.chat_pub.publish(msg)
            
            full_text = ""
            last_chunk = None
            t_start = time.monotonic()
            try:
                response = self.client.models.generate_content_stream(
                    model=model_name,
                    contents=req_contents,
                    config=req_config
                )
                for chunk in response:
                    last_chunk = chunk
                    if chunk.text:
                        chunk_msg = String()
                        chunk_msg.data = json.dumps({"id": msg_id, "text": chunk.text})
                        self.chat_pub.publish(chunk_msg)
                        full_text += chunk.text
                        time.sleep(0.01)
            except Exception as e:
                self.get_logger().error(f"Streaming error: {e}")
                
            t_elapsed = time.monotonic() - t_start
            usage = model_comparator.extract_usage_metrics(last_chunk, model_name, len(str(req_contents)), len(full_text))
            self._record_and_publish_telemetry(model_name, usage, t_elapsed * 1000.0, is_plan_step=True)
            if self.experiment_logger:
                self.experiment_logger.log_brainstorm_turn(sender, model_name, t_elapsed, len(full_text))
                self.experiment_logger.log_api_call(model_name, t_elapsed, success=True)

            return full_text

        self.get_logger().info("\033[93m[RULE-BASED TASK GENERATOR] Formulating Grounded Task Blueprint...\033[0m")
        try:
            # 1. Update real-time TF state and generate deterministic blueprint
            self.workspace_state.update_from_tf(self.tf_buffer)
            blueprint_data, blueprint_text = RuleBasedTaskGenerator.generate_blueprint(self.workspace_state, goal_text=goal_text)

            # Publish the deterministic blueprint directly to the chat stream so the user sees it in the GUI
            blueprint_msg_id = str(uuid.uuid4())
            bp_header = {
                "id": blueprint_msg_id,
                "text": blueprint_text,
                "senderName": "Rule-Based Task Generator (Deterministic Blueprint)",
                "emoji": "📋",
                "role": "generator"
            }
            bp_ros_msg = String()
            bp_ros_msg.data = json.dumps(bp_header)
            self.chat_pub.publish(bp_ros_msg)

            # 2. Single-turn VLA Reasoning with Gemini-4-Argon
            vla_prompt = f"""
You are the Robotics VLA Orchestrator ({robotics_model}). The user's goal is: "{goal_text}".

{blueprint_text}

Instructions:
1. Physical Workspace Assignment: Review the camera image and the Grounded Blueprint above.
   - Follow the specific sequence in the blueprint (Tower Stacking or Multi-Robot Relay/Transfer).
   - For multi-robot relays between outer tables (e.g. Table 1 to Table 3): use the Central Table [0.0, 0.0] as the intermediate staging handoff!
2. Concurrency: Maximize concurrent picks across independent robots where safe.
3. Pre-execution Safety: All actions are validated by the Rule-Based Task Verifier before dispatch to FR3 arms.

Provide a crisp, 2-3 sentence executive summary of your VLA task strategy.
"""
            req_contents = [
                genai_types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
                genai_types.Part.from_text(text=vla_prompt)
            ] if image_bytes else vla_prompt

            sender_label = "Gemini Robotics-ER 2" if robotics_model == "gemini-robotics-er-2-preview" else "Gemini-4-Argon High-Level Brain"
            vla_response = stream_chat(
                sender_label, "🦾", "vla",
                robotics_model, req_contents,
                genai_types.GenerateContentConfig(
                    temperature=0.1,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=256),
                )
            )

            combined_blueprint = f"{blueprint_text}\n\nVLA Task Strategy:\n{vla_response}"
            return combined_blueprint

        except Exception as e:
            self.get_logger().error(f"Failed task generation: {e}")
            return "No blueprint available due to error."

    def _run_agentic_task(self):
        """Agentic loop: Gemini calls functions, we execute them."""
        self.get_logger().info(f"\033[94m[AGENT] Starting Agentic Loop (brain_mode={self.brain_mode})...\033[0m")
        
        image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb) if self.latest_rgb is not None else None
        blueprint = self._brainstorm_spatial_plan(self.user_goal, image_bytes)
        
        prompt_template = getattr(self, 'system_prompt_template', gemini_prompts.SYSTEM_PROMPT)
        static_sys_instruction = prompt_template.format(
            user_goal="Follow the Grounded Blueprint and invoke the robot tool calls (`pick`, `place`, `dual_arm_pick`, `dual_arm_circle`, `dual_arm_place`, `go_home`) with maximum safe concurrency."
        )
        dynamic_goal_text = (
            f"User Goal: {self.user_goal}\n\n"
            f"--- GROUNDED BLUEPRINT & HIGH-LEVEL BRAIN STRATEGY ---\n{blueprint}\n"
            "------------------------------------------------------\n"
            "Invoke the next robot tool call(s) now."
        )
        user_parts = []
        if image_bytes:
            user_parts.append(genai_types.Part.from_bytes(data=image_bytes, mime_type='image/png'))
        user_parts.append(genai_types.Part.from_text(text=dynamic_goal_text))
        contents = [
            genai_types.Content(
                role="user",
                parts=user_parts
            )
        ]
        max_turns = 45
        placement_count = 0
        total_blocks_placed = 0
        premature_text_turns = 0
        is_dual_cell = len(self.robot_bases) == 2
        is_bar_goal = is_dual_cell and any(w in (self.user_goal or "").lower() for w in ("longbar", "bar", "circle", "wave", "cycloid"))
        target_blocks = getattr(self, "experiment_target_blocks", (3 if is_bar_goal else 2) if is_dual_cell else 9)
        if is_dual_cell and target_blocks > 3:
            target_blocks = 3 if is_bar_goal else 2
        dual_place_done = False
        escalate_next_turn = False
        
        for turn in range(max_turns):
            if self.cancel_current_task:
                self.get_logger().warn("\033[93m[WARN] Aborting current agentic loop due to cancellation request!\033[0m")
                break

            if self.brain_mode in ("argon_optimized", "compare_ab"):
                active_turn_model = self.model_name if escalate_next_turn else self.fast_executor_model
                active_thinking_budget = 256 if escalate_next_turn else 0
            elif self.brain_mode == "gemini-robotics-er-2-preview":
                active_turn_model = "gemini-robotics-er-2-preview"
                active_thinking_budget = 512
            else:
                active_turn_model = self.model_name
                active_thinking_budget = 512

            escalate_next_turn = False
            self.get_logger().info(f"\033[94m[AGENT] Turn {turn+1}/{max_turns} [model={active_turn_model}, thinking={active_thinking_budget}]\033[0m")

            if len(contents) > 7:
                contents = [contents[0]] + contents[-6:]
            
            if turn > 0 and turn % 3 == 0 and self.latest_rgb is not None:
                self.get_logger().info("\033[96m[VISION] Injecting fresh camera frame into context...\033[0m")
                fresh_image = gemini_utils.encode_image_to_bytes(self.latest_rgb)
                if fresh_image:
                    contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part.from_bytes(data=fresh_image, mime_type='image/png'),
                                genai_types.Part.from_text(text="[SYSTEM AUTO-REFRESH] Latest overhead camera view.")
                            ]
                        )
                    )
            
            t_gen_start = time.monotonic()
            gen_cfg_kwargs = dict(
                system_instruction=static_sys_instruction,
                temperature=0.0,
                tools=gemini_tools.ROBOT_TOOLS,
            )
            if active_thinking_budget > 0 and "flash-lite" not in str(active_turn_model).lower():
                gen_cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_budget=active_thinking_budget
                )
            response = self.client.models.generate_content(
                model=active_turn_model,
                contents=contents,
                config=genai_types.GenerateContentConfig(**gen_cfg_kwargs),
            )
            t_gen_elapsed = time.monotonic() - t_gen_start
            if self.experiment_logger:
                self.experiment_logger.log_api_call(active_turn_model, t_gen_elapsed, success=True)
            
            if not response.candidates:
                self.get_logger().error("No candidates returned from Gemini.")
                break
                
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                self.get_logger().error("Empty content returned from Gemini.")
                break
                
            func_parts = [p for p in candidate.content.parts if p.function_call]
            usage = model_comparator.extract_usage_metrics(response, active_turn_model, len(static_sys_instruction) + len(dynamic_goal_text), 180)
            if self.experiment_logger:
                self.experiment_logger.record_agent_turn(turn + 1, len(func_parts))

            if func_parts:
                self.get_logger().debug(f"\033[95m[GEMINI] Issued {len(func_parts)} parallel function calls.\033[0m")
                contents.append(candidate.content)
                
                import concurrent.futures
                response_parts = []
                replan_triggered = False
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(func_parts)) as executor:
                    futures = {}
                    for p in func_parts:
                        fc = p.function_call
                        raw_args = dict(fc.args) if fc.args else {}

                        # ── PRE-EXECUTION RULE-BASED SAFETY INTERCEPTION ──
                        is_valid, sanitized_args, verif_msg = self.verifier.verify_action(
                            fc.name, raw_args, self.workspace_state, goal_text=self.user_goal
                        )

                        if not is_valid:
                            escalate_next_turn = True
                            self.get_logger().warn(
                                f"\033[91m[RULE VERIFIER BLOCKED] {fc.name}({raw_args}) -> {verif_msg}\033[0m"
                            )
                            def make_rejected(msg=verif_msg, name=fc.name):
                                return {
                                    "success": False,
                                    "verified": False,
                                    "rejection_reason": msg,
                                    "error_context": f"Action '{name}' rejected by Rule-Based Task Verifier: {msg}. Follow table boundaries and the Rule-Based Blueprint."
                                }
                            futures[executor.submit(make_rejected)] = (fc, raw_args, verif_msg, False)
                        else:
                            if verif_msg and "[INTERCEPT]" in verif_msg:
                                self.get_logger().info(
                                    f"\033[93m[RULE VERIFIER AUTO-CORRECT] {verif_msg}\033[0m"
                                )
                            if self.experiment_logger:
                                self.experiment_logger.log_action_dispatched(
                                    robot_id=sanitized_args.get("robot", "global"),
                                    action=fc.name,
                                    target=sanitized_args.get("object_label") or sanitized_args.get("anchor_block") or sanitized_args.get("target"),
                                    params=sanitized_args
                                )
                            try:
                                import uuid
                                step_msg = String()
                                step_msg.data = json.dumps({
                                    "id": str(uuid.uuid4()),
                                    "text": f"Dispatched `{fc.name}({json.dumps(sanitized_args)})`",
                                    "senderName": f"Gemini-4-Argon ({self.model_name})",
                                    "emoji": "🦾",
                                    "role": "vla"
                                })
                                self.chat_pub.publish(step_msg)
                            except Exception:
                                pass
                            futures[executor.submit(self._execute_function, fc.name, sanitized_args)] = (fc, sanitized_args, verif_msg, True)
                    
                    for future in concurrent.futures.as_completed(futures):
                        fc, used_args, verif_msg, was_dispatched = futures[future]
                        self.get_logger().info(f"\033[96m[TOOL] Result for {fc.name} (args: {used_args})\033[0m")
                        try:
                            res = future.result()
                            duration = res.get("elapsed_sec", 0.0)
                            if self.experiment_logger and was_dispatched:
                                self.experiment_logger.log_action_result(
                                    robot_id=used_args.get("robot", "global"),
                                    action=fc.name,
                                    success=res.get("success", False),
                                    duration_sec=duration,
                                    message=res.get("message", res.get("rejection_reason", "")),
                                    target=used_args.get("object_label") or used_args.get("anchor_block") or used_args.get("target")
                                )
                            if fc.name == "pick" and not res.get("success", False):
                                escalate_next_turn = True
                                r_key = self._normalize_wait_key(used_args.get("robot", "FR3_1"))
                                if hasattr(self.verifier, "robot_holding") and r_key in self.verifier.robot_holding:
                                    self.verifier.robot_holding[r_key] = None
                            elif fc.name == "dual_arm_pick" and not res.get("success", False):
                                escalate_next_turn = True
                                if hasattr(self.verifier, "robot_holding"):
                                    self.verifier.robot_holding["FR3_1"] = None
                                    self.verifier.robot_holding["FR3_2"] = None
                            eff_act = str(used_args.get("action") or fc.name).strip().lower()
                            if is_bar_goal:
                                if eff_act in ("dual_arm_pick", "dual_arm_circle", "dual_arm_draw_circle", "dual_arm_motion", "dual_arm_place", "pick", "place") and res.get("success", False):
                                    total_blocks_placed += 1
                                    if self.active_trial_stats is not None:
                                        self.active_trial_stats["blocks_placed"] = total_blocks_placed
                                if eff_act == "dual_arm_place" and res.get("success", False):
                                    dual_place_done = True
                            elif eff_act in ("place", "place_relative", "dual_arm_place") and res.get("success", False):
                                placement_count += 1
                                total_blocks_placed += 1
                                if self.active_trial_stats is not None:
                                    self.active_trial_stats["blocks_placed"] = total_blocks_placed
                            if fc.name == "replan":
                                replan_triggered = True
                                if self.experiment_logger:
                                    self.experiment_logger.record_replan("Agent requested replan")
                        except Exception as e:
                            import traceback
                            self.get_logger().error(f"Function {fc.name} failed with exception: {e}")
                            self.get_logger().error(traceback.format_exc())
                            res = {"error": str(e), "success": False}
                            if self.experiment_logger:
                                self.experiment_logger.log_action_result(
                                    robot_id=used_args.get("robot", "global"),
                                    action=fc.name,
                                    success=False,
                                    duration_sec=0.0,
                                    message=str(e),
                                    target=used_args.get("object_label") or used_args.get("anchor_block") or used_args.get("target")
                                )
                            
                        response_parts.append(
                            genai_types.Part.from_function_response(
                                name=fc.name,
                                response=res
                            )
                        )
                        
                verified_in_turn = sum(1 for _, _, _, was_disp in futures.values() if was_disp)
                self._record_and_publish_telemetry(
                    active_turn_model, usage, t_gen_elapsed * 1000.0, len(func_parts), verified_in_turn
                )
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=response_parts
                    )
                )
                
                if replan_triggered:
                    self.get_logger().info("\033[93m[REPLAN] Initiating mid-task rule-based re-planning...\033[0m")
                    fresh_image = gemini_utils.encode_image_to_bytes(self.latest_rgb) if self.latest_rgb is not None else None
                    new_blueprint = self._brainstorm_spatial_plan("REPLAN AND RECOVER. " + self.user_goal, fresh_image)
                    contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part.from_text(text=f"[SYSTEM REPLAN RESULTS] Updated Grounded Blueprint:\n{new_blueprint}")
                            ]
                        )
                    )
                    
                if (is_bar_goal and dual_place_done) or (not is_bar_goal and total_blocks_placed >= target_blocks):
                    self.get_logger().info(f"\033[92m[DONE] Target {total_blocks_placed}/{target_blocks} milestones reached!\033[0m")
                    break

                if placement_count >= 3:
                    self.get_logger().info("\033[96m[AUTO-VERIFY] 3 placements completed. Triggering auto-verification...\033[0m")
                    placement_count = 0
                    verify_res = self._fn_verify_tower()
                    if self.experiment_logger:
                        self.experiment_logger.log_event("physics", "auto_verify_verdict", verify_res)
                    if not verify_res.get("success", True):
                         contents.append(
                            genai_types.Content(
                                role="user",
                                parts=[
                                    genai_types.Part.from_text(text=f"[SYSTEM WARNING] Auto-verification failed! Issues: {verify_res.get('issues')}. Please adapt your plan.")
                                ]
                            )
                        )
            else:
                self._record_and_publish_telemetry(active_turn_model, usage, t_gen_elapsed * 1000.0, 0, 0)
                text_parts = []
                for p in candidate.content.parts:
                    if getattr(p, 'text', None):
                        text_parts.append(p.text)
                
                final_text = " ".join(text_parts) if text_parts else "No text response."
                if is_dual_cell and not dual_place_done and premature_text_turns < 2 and any(w in (self.user_goal or "").lower() for w in ("longbar", "bar", "circle", "place")):
                    premature_text_turns += 1
                    next_hint = (
                        "Call `dual_arm_pick(object_label='LongBar', offset_1=-0.25, offset_2=0.25, speed='fast')` now."
                        if total_blocks_placed == 0
                        else (
                            "Now call `dual_arm_circle(radius=0.08, cycles=1, plane='XY', speed='fast')` followed by `dual_arm_place(x=0.0, y=0.0, speed='fast')`."
                            if total_blocks_placed == 1
                            else "Now call `dual_arm_place(x=0.0, y=0.0, speed='fast')` to complete the LongBar placement."
                        )
                    )
                    contents.append(candidate.content)
                    contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=f"[SYSTEM] Only {total_blocks_placed}/3 bimanual LongBar steps completed. {next_hint}")]
                        )
                    )
                    continue

                if len(self.robot_bases) == 3 and total_blocks_placed < target_blocks and premature_text_turns < 2 and "tower" in (self.user_goal or "").lower():
                    premature_text_turns += 1
                    contents.append(candidate.content)
                    contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part.from_text(
                                    text=f"[SYSTEM] Only {total_blocks_placed}/{target_blocks} blocks have been placed so far (currently holding: {self.verifier.robot_holding}). Continue invoking `pick` and `place` tool calls until all {target_blocks} blocks are placed on the central tower."
                                )
                            ]
                        )
                    )
                    continue

                self.get_logger().info(f"\033[92m[DONE] Agent finished: {final_text}\033[0m")
                try:
                    import uuid
                    done_msg = String()
                    done_msg.data = json.dumps({
                        "id": str(uuid.uuid4()),
                        "text": final_text,
                        "senderName": f"Gemini-4-Argon ({self.model_name})",
                        "emoji": "✅",
                        "role": "vla"
                    })
                    self.chat_pub.publish(done_msg)
                except Exception:
                    pass
                break

        # Finalize trial metrics if experiment logger is active
        if self.experiment_logger:
            try:
                self.workspace_state.update_from_tf(self.tf_buffer)
                summary_st = self.workspace_state.get_summary()
                placed_count = summary_st.get("tower", {}).get("layers", 0)
                target_blocks = getattr(self, "experiment_target_blocks", 9)
                is_success = (placed_count >= target_blocks)
                self.experiment_logger.finalize_trial(
                    task_success=is_success,
                    blocks_placed=placed_count,
                    blocks_target=target_blocks,
                    tower_stable=True,
                    final_tower_height_tf=placed_count,
                    exit_status="COMPLETED"
                )
            except Exception as e:
                self.get_logger().error(f"Failed to finalize trial metrics: {e}")

    def _execute_function(self, name: str, args: dict) -> dict:
        """Dispatch function calls to actual robot controllers."""
        try:
            effective_name = str(args.get("action") or name).strip().lower()
            result = None
            if effective_name == "detect_objects":
                result = {"objects": self._fn_detect_objects()}
            elif effective_name == "pick":
                target_block = args.get("target") or args.get("object_label")
                if str(target_block).lower() in ("longbar", "long_bar", "heavyenginepart", "heavy_engine_part"):
                    result = self._fn_dual_arm_pick(
                        target_block,
                        float(args.get("offset_1", -0.25)),
                        float(args.get("offset_2", 0.25)),
                        args.get("speed", "fast")
                    )
                else:
                    result = self._fn_pick(args.get("robot", "FR3_1"), target_block, args.get("speed", "fast"), float(args.get("approach_height", 0.1)))
                    # Auto-retry / enriched error context on pick failure
                    if not result.get("success", True):
                        self.get_logger().warn("Pick failed. Enclosing fresh workspace status.")
                        self.workspace_state.update_from_tf(self.tf_buffer)
                        status = self.workspace_state.get_summary()
                        result["error_context"] = f"Pick failed. Current workspace status: {json.dumps(status)}. Suggest calling replan or try an alternative."
            elif effective_name == "place":
                result = self._fn_place(args.get("robot", "FR3_1"), float(args.get("x", 0.0)), float(args.get("y", 0.0)), args.get("speed", "fast"), float(args.get("approach_height", 0.1)))
            elif effective_name == "place_relative":
                result = self._fn_place_relative(args.get("robot", "FR3_1"), args.get("anchor_block"), args.get("relation"), args.get("speed", "fast"), float(args.get("approach_height", 0.1)))
            elif effective_name == "dual_arm_pick":
                result = self._fn_dual_arm_pick(
                    args.get("target") or args.get("object_label", "LongBar"),
                    float(args.get("offset_1", -0.25)),
                    float(args.get("offset_2", 0.25)),
                    args.get("speed", "fast")
                )
            elif effective_name in ("dual_arm_circle", "dual_arm_draw_circle", "dual_arm_motion"):
                result = self._fn_dual_arm_circle(
                    float(args.get("radius", 0.08)),
                    int(args.get("cycles", 1)),
                    str(args.get("plane", "XY")),
                    args.get("speed", "fast")
                )
            elif effective_name == "dual_arm_place":
                result = self._fn_dual_arm_place(
                    float(args.get("x", 0.0)),
                    float(args.get("y", 0.0)),
                    args.get("speed", "fast")
                )
            elif effective_name == "verify_tower":
                result = self._fn_verify_tower()
            elif effective_name == "go_home":
                result = self._fn_go_home(args.get("robot", "FR3_1"))
            elif effective_name == "get_workspace_status":
                result = self._fn_get_status()
            elif effective_name == "replan":
                result = self._fn_replan()
            else:
                result = {"error": f"Unknown function: {effective_name}"}
                
            # Log action history
            if name in ["pick", "place", "go_home", "dual_arm_pick", "dual_arm_circle", "dual_arm_place"]:
                self.workspace_state.record_action(f"{name} {args}", result.get("success", True), result.get("message", ""))
                
            return result
        except Exception as e:
            self.get_logger().error(f"Error executing {name}: {e}")
            self.workspace_state.record_action(f"{name} {args}", False, str(e))
            return {"error": str(e)}

    def _wait_for_action_complete(self, robot_id: str, timeout=30.0, clear_before_wait: bool = False):
        """Wait for the controller to publish a result for a specific robot."""
        wait_key = self._normalize_wait_key(robot_id)
        if clear_before_wait:
            self.action_results.pop(wait_key, None)
            self.action_results.pop(str(robot_id), None)
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.cancel_current_task:
                return {"success": False, "message": "Action aborted due to task cancellation.", "elapsed_sec": round(time.time() - start_time, 4)}
            if wait_key in self.action_results:
                res = self.action_results.pop(wait_key)
                if "elapsed_sec" not in res:
                    res["elapsed_sec"] = round(time.time() - start_time, 4)
                return res
            if str(robot_id) in self.action_results:
                res = self.action_results.pop(str(robot_id))
                if "elapsed_sec" not in res:
                    res["elapsed_sec"] = round(time.time() - start_time, 4)
                return res
            time.sleep(0.05)  # Yield to the MultiThreadedExecutor
        return {"success": False, "message": f"Timeout waiting for controller for robot {wait_key}", "elapsed_sec": round(time.time() - start_time, 4)}


    # Concrete Primitive Implementations

    def _fn_detect_objects(self) -> list:
        detections = []
        if self.latest_rgb is not None:
            image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
            if image_bytes:
                result_text = self._call_gemini(
                    image_bytes, gemini_prompts.DETECT_BLOCKS_PROMPT, thinking_budget=0)
                detections = gemini_utils.parse_gemini_response(result_text)
        self.last_detections = detections

        # Enrich detections with TF-based proximity data
        block_positions = self._query_block_positions()
        if block_positions:
            # Build a proximity summary for each robot
            proximity_info = []
            for robot_name, base_xy in self.robot_bases.items():
                distances = []
                for block_name, pos in block_positions.items():
                    d = np.hypot(pos[0] - base_xy[0], pos[1] - base_xy[1])
                    distances.append({"block": block_name, "world_xy": [round(pos[0], 3), round(pos[1], 3)], "distance_m": round(d, 3)})
                distances.sort(key=lambda x: x["distance_m"])
                proximity_info.append({"robot": robot_name, "blocks_by_distance": distances})
            
            # Attach proximity data to the detection result
            return {"visual_detections": detections, "proximity": proximity_info}

        msg = String()
        msg.data = json.dumps(detections)
        self.detection_pub.publish(msg)
        return detections

    def _query_block_positions(self) -> dict:
        """Query TF for world-frame XY positions of all 9 blocks."""
        positions = {}
        for i in range(1, 10):
            block_name = f"Block{i}"
            try:
                trans = self.tf_buffer.lookup_transform(
                    'world', block_name, rclpy.time.Time(), timeout=Duration(seconds=0.1))
                x = trans.transform.translation.x
                y = trans.transform.translation.y
                positions[block_name] = (x, y)
            except Exception:
                pass  # Block may not exist or TF not yet available
        return positions

    def _fn_pick(self, robot: str, object_label: str, speed: str = 'fast', approach_height: float = 0.1) -> dict:
        wait_key = self._normalize_wait_key(robot)
        self.action_results.pop(wait_key, None)
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": wait_key,
            "target": object_label,
            "speed": speed,
            "approach_height": approach_height
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(wait_key, timeout=25.0)

    def _fn_place(self, robot: str, x: float = 0.0, y: float = 0.0, speed: str = 'fast', approach_height: float = 0.1) -> dict:
        wait_key = self._normalize_wait_key(robot)
        self.action_results.pop(wait_key, None)
        msg = String()
        msg.data = json.dumps({
            "action": "place",
            "robot": wait_key,
            "x": x,
            "y": y,
            "speed": speed,
            "approach_height": approach_height
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(wait_key, timeout=25.0)

    def _fn_place_relative(self, robot: str, anchor_block: str, relation: str, speed: str = 'fast', approach_height: float = 0.1) -> dict:
        """Resolve a relative placement request into absolute coordinates via TF."""
        try:
            # Clean block name (e.g., 'Red Cube' -> 'Block1')
            block_key = gemini_utils.resolve_block_key(anchor_block)
            if not block_key:
                return {"success": False, "message": f"Could not resolve anchor block name: {anchor_block}"}
            
            # Lookup anchor in TF
            transform = self.tf_buffer.lookup_transform('world', block_key, rclpy.time.Time())
            anchor_x = transform.transform.translation.x
            anchor_y = transform.transform.translation.y
            
            # Apply offset
            block_size = 0.045 # 4.5cm block width + tolerance
            target_x, target_y = anchor_x, anchor_y
            
            if relation == "left_of":
                target_y += block_size
            elif relation == "right_of":
                target_y -= block_size
            elif relation == "front_of":
                target_x += block_size
            elif relation == "back_of":
                target_x -= block_size
            elif relation == "on_top_of":
                pass # Same X, Y. The multi_robot_controller dynamically computes Z.
            else:
                return {"success": False, "message": f"Unknown relation: {relation}"}
                
            self.get_logger().info(f"\033[96m[TOOL] place_relative resolved {relation} {anchor_block} to X:{target_x:.3f}, Y:{target_y:.3f}\033[0m")
            return self._fn_place(robot, float(target_x), float(target_y), speed, approach_height)
        except Exception as e:
            self.get_logger().error(f"Error in place_relative: {e}")
            return {"success": False, "message": f"TF lookup failed for {anchor_block}: {e}"}


    def _fn_dual_arm_pick(self, object_label: str, offset_1: float = -0.25, offset_2: float = 0.25, speed: str = 'fast') -> dict:
        """Dispatch synchronized bimanual pick across FR3_1 and FR3_2."""
        self.action_results.pop("FR3_1", None)
        self.action_results.pop("FR3_2", None)
        self.action_results.pop("global", None)
        msg = String()
        msg.data = json.dumps({
            "action": "dual_arm_pick",
            "target": object_label,
            "offset_1": offset_1,
            "offset_2": offset_2,
            "speed": speed
        })
        self.action_pub.publish(msg)
        res = self._wait_for_action_complete("global", timeout=35.0)
        if res.get("success", False):
            return {"success": True, "FR3_1": res, "FR3_2": res, "message": res.get("message", "Dual-arm pick succeeded.")}
        res1 = self._wait_for_action_complete("FR3_1", timeout=5.0)
        res2 = self._wait_for_action_complete("FR3_2", timeout=5.0)
        return {"success": res1.get("success", False) and res2.get("success", False), "FR3_1": res1, "FR3_2": res2}

    def _fn_dual_arm_circle(self, radius: float = 0.08, cycles: int = 1, plane: str = 'XY', speed: str = 'fast') -> dict:
        """Dispatch synchronized bimanual circular closed-chain trajectory."""
        self.action_results.pop("global", None)
        msg = String()
        msg.data = json.dumps({
            "action": "dual_arm_circle",
            "radius": float(radius),
            "cycles": int(cycles),
            "plane": str(plane),
            "speed": str(speed)
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete("global", timeout=45.0)

    def _fn_dual_arm_place(self, x: float = 0.0, y: float = 0.0, speed: str = 'fast') -> dict:
        """Dispatch synchronized bimanual Cartesian placement."""
        self.action_results.pop("FR3_1", None)
        self.action_results.pop("FR3_2", None)
        self.action_results.pop("global", None)
        msg = String()
        msg.data = json.dumps({
            "action": "dual_arm_place",
            "x": float(x),
            "y": float(y),
            "speed": speed
        })
        self.action_pub.publish(msg)
        res = self._wait_for_action_complete("global", timeout=35.0)
        if res.get("success", False):
            return res
        res1 = self._wait_for_action_complete("FR3_1", timeout=5.0)
        res2 = self._wait_for_action_complete("FR3_2", timeout=5.0)
        return {"success": res1.get("success", False) or res2.get("success", False), "FR3_1": res1, "FR3_2": res2}

    def _fn_go_home(self, robot: str) -> dict:
        wait_key = self._normalize_wait_key(robot)
        self.action_results.pop(wait_key, None)
        msg = String()
        msg.data = json.dumps({
            "action": "go_home",
            "robot": wait_key,
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(wait_key, timeout=20.0)

    def _fn_verify_tower(self) -> dict:
        # Give physics a moment to settle
        import time
        time.sleep(0.5)
        self.action_results.pop("global", None)
        msg = String()
        msg.data = json.dumps({
            "action": "verify_tower"
        })
        self.action_pub.publish(msg)
        
        res = self._wait_for_action_complete("global", timeout=10.0)
        if not res.get("success", False):
            return {"success": False, "issues": "Failed to query tower verification state."}

        if self.latest_rgb is None:
            return {"success": True, "issues": "", "assessment": res.get("message", "Verified via 3D TF workspace state.")}

        # Take new picture when overhead camera is active
        image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        if not image_bytes:
            return {"success": True, "issues": "", "assessment": res.get("message", "Verified via 3D TF workspace state.")}
        verify_response = self._call_gemini(
            image_bytes, 
            gemini_prompts.VERIFY_PLACEMENT_PROMPT,
            thinking_budget=512
        )
        try:
            return gemini_utils.parse_gemini_response(verify_response)
        except Exception as e:
            return {"success": False, "issues": f"Failed to parse verify response: {e}"}

    def _fn_get_status(self) -> dict:
        self.workspace_state.update_from_tf(self.tf_buffer)
        return self.workspace_state.get_summary()

    def _fn_replan(self) -> dict:
        """Trigger a fresh brainstorm."""
        self.get_logger().warn("Replanning requested by agent.")
        image_bytes = None
        if self.latest_rgb is not None:
            image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        
        # We return a special dict that _execute_function handles
        return {"action": "replan_requested"}


def main(args=None):
    rclpy.init(args=args)
    node = GeminiRoboticsNode()
    from rclpy.executors import MultiThreadedExecutor
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()


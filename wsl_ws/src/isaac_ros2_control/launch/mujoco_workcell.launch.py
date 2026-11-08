from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    mode_arg = DeclareLaunchArgument(
        "workcell_mode",
        default_value="3",
        description="Workcell mode: 1 (3-Arm Tower), 2 (Dual-Arm Conveyor), 3 (EFE Deformable & SDL Assembly)",
    )
    viewer_arg = DeclareLaunchArgument(
        "enable_viewer",
        default_value="false",
        description="Open WSLg passive MuJoCo viewer window if true",
    )

    mujoco_node = Node(
        package="isaac_ros2_control",
        executable="mujoco_sim_node",
        name="mujoco_sim_node",
        output="screen",
        parameters=[
            {
                "workcell_mode": LaunchConfiguration("workcell_mode"),
                "enable_viewer": LaunchConfiguration("enable_viewer"),
            }
        ],
    )

    controller_node = Node(
        package="isaac_ros2_control",
        executable="conveyor_dual_controller",
        name="conveyor_dual_controller",
        output="screen",
        parameters=[{"use_sim_time": True, "mode": "gemini"}],
    )

    gemini_node = Node(
        package="isaac_ros2_control",
        executable="conveyor_gemini_node",
        name="gemini_robotics_node",
        output="screen",
        parameters=[{"use_sim_time": True}],
    )

    monitor_node = Node(
        package="isaac_ros2_control",
        executable="monitoring_agent_node",
        name="monitoring_agent_node",
        output="screen",
        parameters=[{"use_sim_time": True}],
    )

    return LaunchDescription([mode_arg, viewer_arg, mujoco_node, controller_node, gemini_node, monitor_node])

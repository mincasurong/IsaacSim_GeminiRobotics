"""General launch file for the Multi-Robot Controller.

Usage:
    ros2 launch isaac_ros2_control multi_robot_controller.launch.py
    ros2 launch isaac_ros2_control multi_robot_controller.launch.py mode:=gemini
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    mode_arg = DeclareLaunchArgument(
        'mode',
        default_value='rule_based',
        description="Operational mode: 'rule_based' (autonomous) or 'gemini' (orchestrated)"
    )

    controller_node = Node(
        package='isaac_ros2_control',
        executable='multi_robot_controller',
        name='multi_robot_controller',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'mode': LaunchConfiguration('mode'),
            'tower_x': 0.0,
            'tower_y': 0.0,
            'block_height': 0.06,
            'hover_height': 0.15,
            'steps_per_phase': 40,
            'dwell_steps': 15,
        }],
    )

    return LaunchDescription([
        mode_arg,
        controller_node,
    ])

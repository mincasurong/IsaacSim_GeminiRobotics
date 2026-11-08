"""Launch file for Rule-Based Multi-Robot Pick-and-Place Tower Stacking.

Executes autonomous turn-based multi-robot motion planning using TF pose tracking
and kinematics without requiring external VLM / LLM API calls.

Usage:
    ros2 launch isaac_ros2_control multi_robot_rule_based.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    controller_node = Node(
        package='isaac_ros2_control',
        executable='multi_robot_controller',
        name='multi_robot_controller',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'mode': 'rule_based',
            'tower_x': 0.0,
            'tower_y': 0.0,
            'block_height': 0.06,
            'hover_height': 0.15,
            'steps_per_phase': 40,
            'dwell_steps': 15,
        }],
    )

    return LaunchDescription([
        controller_node,
    ])

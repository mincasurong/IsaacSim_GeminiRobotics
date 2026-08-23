"""Launch file for Gemini Robotics-ER integration with Isaac Sim.

Launches the Gemini Robotics VLM node alongside the multi-robot controller
in 'gemini' mode for vision-driven agentic task orchestration.

Usage:
    ros2 launch isaac_ros2_control gemini_controller.launch.py
    ros2 launch isaac_ros2_control gemini_controller.launch.py env_file:=/path/to/.env
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    env_file_arg = DeclareLaunchArgument(
        'env_file',
        default_value='',
        description='Path to the private .env file containing the Gemini API key'
    )

    detection_interval_arg = DeclareLaunchArgument(
        'detection_interval',
        default_value='0.0',
        description='Automatic detection interval in seconds (0 = manual only via services)'
    )

    gemini_node = Node(
        package='isaac_ros2_control',
        executable='gemini_robotics_node',
        name='gemini_robotics_node',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'env_file': LaunchConfiguration('env_file'),
            'detection_interval': LaunchConfiguration('detection_interval'),
        }],
    )

    controller_node = Node(
        package='isaac_ros2_control',
        executable='multi_robot_controller',
        name='multi_robot_controller',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'mode': 'gemini',
            'tower_x': 0.0,
            'tower_y': 0.0,
            'block_height': 0.06,
            'hover_height': 0.15,
            'steps_per_phase': 40,
            'dwell_steps': 15,
        }],
    )

    return LaunchDescription([
        env_file_arg,
        detection_interval_arg,
        gemini_node,
        controller_node,
    ])

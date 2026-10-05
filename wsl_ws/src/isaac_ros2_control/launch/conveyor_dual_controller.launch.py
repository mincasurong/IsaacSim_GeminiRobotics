from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='isaac_ros2_control',
            executable='conveyor_dual_controller',
            name='conveyor_dual_controller',
            output='screen',
            parameters=[
                {'mode': 'gemini'},
            ]
        ),
        Node(
            package='isaac_ros2_control',
            executable='conveyor_gemini_node',
            name='conveyor_gemini_node',
            output='screen',
        ),
        Node(
            package='isaac_ros2_control',
            executable='vision_tracker_node',
            name='vision_tracker_node',
            output='screen',
        ),
        Node(
            package='isaac_ros2_control',
            executable='monitoring_agent_node',
            name='monitoring_agent_node',
            output='screen',
            parameters=[{
                'summary_interval': 25.0,
            }],
        )
    ])

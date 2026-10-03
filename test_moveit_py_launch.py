import rclpy
from rclpy.node import Node
from moveit.planning import MoveItPy
from moveit_configs_utils import MoveItConfigsBuilder
from launch import LaunchDescription
from launch_ros.actions import Node as LaunchNode
from launch.actions import ExecuteProcess
import sys

# To test this via launch
def generate_launch_description():
    moveit_config = (
        MoveItConfigsBuilder('multi_robot_moveit_config', package_name='multi_robot_moveit_config')
        .robot_description(file_path='config/three_robot_scene.urdf.xacro')
        .robot_description_semantic(file_path='config/three_robot_scene.srdf')
        .trajectory_execution(file_path='config/moveit_controllers.yaml')
        .planning_pipelines(pipelines=['ompl'])
        .to_moveit_configs()
    )
    return LaunchDescription([
        LaunchNode(
            package='isaac_ros2_control',
            executable='multi_robot_moveit_controller',
            output='screen',
            parameters=[moveit_config.to_dict()]
        )
    ])

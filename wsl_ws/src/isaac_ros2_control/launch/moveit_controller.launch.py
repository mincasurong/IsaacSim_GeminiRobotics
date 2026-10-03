import os
from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder

def generate_launch_description():
    moveit_config = (
        MoveItConfigsBuilder("multi_robot_moveit_config", package_name="multi_robot_moveit_config")
        .robot_description(file_path="config/three_robot_scene.urdf.xacro")
        .robot_description_semantic(file_path="config/three_robot_scene.srdf")
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .planning_pipelines(pipelines=["ompl"])
        .moveit_cpp(file_path="config/moveit_cpp.yaml")
        .to_moveit_configs()
    )

    config_dict = moveit_config.to_dict()
    config_dict.pop('planning_pipelines', None)

    moveit_py_node = Node(
        package='isaac_ros2_control',
        executable='multi_robot_moveit_controller',
        output='screen',
        parameters=[
            config_dict,
            {'use_sim_time': False, 'planning_pipelines.pipeline_names': ['ompl']},
            {'plan_request_params.planning_attempts': 1,
             'plan_request_params.planning_pipeline': 'ompl',
             'plan_request_params.max_velocity_scaling_factor': 1.0,
             'plan_request_params.max_acceleration_scaling_factor': 1.0}
        ],
    )
    
    adapter_node = Node(
        package='isaac_ros2_control',
        executable='trajectory_adapter',
        output='screen'
    )

    return LaunchDescription([adapter_node, moveit_py_node])

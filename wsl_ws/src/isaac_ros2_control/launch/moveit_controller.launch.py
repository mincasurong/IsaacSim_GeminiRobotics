import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder
import yaml

def load_yaml(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except EnvironmentError:
        return None

def generate_launch_description():
    # Build MoveIt configs manually since we don't have a full moveit_setup_assistant package
    urdf_pkg = get_package_share_directory('multi_robot_description')
    import subprocess
    urdf_content = subprocess.check_output(f"xacro {os.path.join(urdf_pkg, 'urdf', 'three_robot_scene.urdf.xacro')}", shell=True).decode('utf-8')
    robot_description = {'robot_description': urdf_content}

    moveit_pkg = get_package_share_directory('multi_robot_moveit_config')
    with open(os.path.join(moveit_pkg, 'config', 'three_robot_scene.srdf'), 'r') as f:
        semantic_content = f.read()
    robot_description_semantic = {'robot_description_semantic': semantic_content}

    kinematics_yaml = load_yaml('multi_robot_moveit_config', 'config/kinematics.yaml')
    robot_description_kinematics = {'robot_description_kinematics': kinematics_yaml}

    ompl_planning_pipeline_config = {
        'ompl': {
            'planning_plugin': 'ompl_interface/OMPLPlanner',
            'request_adapters': """default_planner_request_adapters/AddTimeOptimalParameterization default_planner_request_adapters/FixWorkspaceBounds default_planner_request_adapters/FixStartStateBounds default_planner_request_adapters/FixStartStateCollision default_planner_request_adapters/FixStartStatePathConstraints""",
            'start_state_max_bounds_error': 0.1,
        }
    }
    ompl_planning_yaml = load_yaml('multi_robot_moveit_config', 'config/ompl_planning.yaml')
    ompl_planning_pipeline_config['ompl'].update(ompl_planning_yaml)

    controllers_yaml = load_yaml('multi_robot_moveit_config', 'config/moveit_controllers.yaml')
    trajectory_execution = {
        'moveit_manage_controllers': True,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.01,
    }

    joint_limits_yaml = load_yaml('multi_robot_moveit_config', 'config/joint_limits.yaml')
    robot_description_planning = {'robot_description_planning': joint_limits_yaml}
    
    # moveit_py parameter name convention requires passing "robot_description", "robot_description_semantic" etc directly.
    # plus it needs a `planning_pipelines` list.
    moveit_controllers = {
        'moveit_simple_controller_manager': controllers_yaml['moveit_simple_controller_manager'],
        'moveit_controller_manager': 'moveit_simple_controller_manager/MoveItSimpleControllerManager',
    }

    moveit_py_node = Node(
        package='isaac_ros2_control',
        executable='multi_robot_moveit_controller',
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            robot_description_kinematics,
            robot_description_planning,
            ompl_planning_pipeline_config,
            trajectory_execution,
            moveit_controllers,
            {'use_sim_time': False, 'planning_pipelines': ['ompl']},
        ],
    )
    
    # We also need the trajectory_adapter node
    adapter_node = Node(
        package='isaac_ros2_control',
        executable='trajectory_adapter',
        output='screen'
    )

    return LaunchDescription([adapter_node, moveit_py_node])

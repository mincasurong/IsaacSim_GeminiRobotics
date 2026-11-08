from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os
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
    # Load URDF
    urdf_pkg = get_package_share_directory('multi_robot_description')
    import subprocess
    urdf_content = subprocess.check_output(f"xacro {os.path.join(urdf_pkg, 'urdf', 'three_robot_scene.urdf.xacro')}", shell=True).decode('utf-8')
    robot_description = {'robot_description': urdf_content}

    # Load SRDF
    moveit_pkg = get_package_share_directory('multi_robot_moveit_config')
    with open(os.path.join(moveit_pkg, 'config', 'three_robot_scene.srdf'), 'r') as f:
        semantic_content = f.read()
    robot_description_semantic = {'robot_description_semantic': semantic_content}

    # Load Kinematics
    kinematics_yaml = load_yaml('multi_robot_moveit_config', 'config/kinematics.yaml')
    robot_description_kinematics = {'robot_description_kinematics': kinematics_yaml}

    # Load Planning
    ompl_planning_pipeline_config = {
        'move_group': {
            'planning_plugin': 'ompl_interface/OMPLPlanner',
            'request_adapters': """default_planner_request_adapters/AddTimeOptimalParameterization default_planner_request_adapters/FixWorkspaceBounds default_planner_request_adapters/FixStartStateBounds default_planner_request_adapters/FixStartStateCollision default_planner_request_adapters/FixStartStatePathConstraints""",
            'start_state_max_bounds_error': 0.1,
        }
    }
    ompl_planning_yaml = load_yaml('multi_robot_moveit_config', 'config/ompl_planning.yaml')
    ompl_planning_pipeline_config['move_group'].update(ompl_planning_yaml)

    # Load Trajectory Execution
    controllers_yaml = load_yaml('multi_robot_moveit_config', 'config/moveit_controllers.yaml')
    trajectory_execution = {
        'moveit_manage_controllers': True,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.01,
    }

    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            robot_description_kinematics,
            ompl_planning_pipeline_config,
            trajectory_execution,
            {'use_sim_time': False},
        ],
    )

    return LaunchDescription([move_group_node])

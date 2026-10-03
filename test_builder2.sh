#!/bin/bash
source /opt/ros/jazzy/setup.bash
source /mnt/d/git/IsaacSim_Gemini/wsl_ws/install/setup.bash
python3 -c "
from moveit_configs_utils import MoveItConfigsBuilder
config = MoveItConfigsBuilder('multi_robot_moveit_config', package_name='multi_robot_moveit_config').robot_description(file_path='config/three_robot_scene.urdf.xacro').robot_description_semantic(file_path='config/three_robot_scene.srdf').planning_pipelines(pipelines=['ompl']).to_dict()
import pprint
pprint.pprint(config.get('ompl', {}))
"

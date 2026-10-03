#!/bin/bash
source /opt/ros/jazzy/setup.bash
source /mnt/d/git/IsaacSim_Gemini/wsl_ws/install/setup.bash
python3 -c "
from moveit.planning import MoveItPy
from moveit_configs_utils import MoveItConfigsBuilder

config = MoveItConfigsBuilder('multi_robot_moveit_config', package_name='multi_robot_moveit_config').robot_description(file_path='config/three_robot_scene.urdf.xacro').robot_description_semantic(file_path='config/three_robot_scene.srdf').planning_pipelines(pipelines=['ompl']).to_dict()

# Flatten dictionary
def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = f'{parent_key}{sep}{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

flat_config = flatten_dict(config)
flat_config.pop('planning_pipelines', None)
flat_config['planning_pipelines.pipeline_names'] = ['ompl']

import pprint
pprint.pprint(flat_config)

try:
    moveit_py = MoveItPy(node_name='test_node', config_dict=flat_config)
    print('SUCCESS! config_dict works!')
except Exception as e:
    print('FAILED:', e)
"

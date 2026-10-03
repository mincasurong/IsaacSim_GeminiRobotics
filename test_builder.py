from moveit_configs_utils import MoveItConfigsBuilder
config = MoveItConfigsBuilder('multi_robot_moveit_config', package_name='multi_robot_moveit_config').moveit_cpp().to_dict()
print(config.get('moveit_cpp', 'NO_MOVEIT_CPP'))

#!/bin/bash
source /opt/ros/jazzy/setup.bash
source /mnt/d/git/IsaacSim_Gemini/wsl_ws/install/setup.bash
ros2 run joint_state_publisher joint_state_publisher --ros-args -p source_list:="['/fr3_1/joint_states', '/fr3_2/joint_states', '/fr3_3/joint_states']"

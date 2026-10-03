#!/bin/bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub -1 /fr3_1/gemini_action_cmd std_msgs/msg/String "{data: '{\"action\": \"go_home\"}'}"

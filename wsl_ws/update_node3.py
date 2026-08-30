# -*- coding: utf-8 -*-
f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

content = content.replace("model_to_use = 'gemini-2.5-pro'", "model_to_use = gemini_config.get_planner_model()")

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Fixed model_to_use")

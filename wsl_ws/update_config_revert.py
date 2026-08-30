# -*- coding: utf-8 -*-
f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_config.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

content = content.replace("gemini-robotics-er-2", "gemini-robotics-er-2-preview")

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Reverted gemini_config.py")

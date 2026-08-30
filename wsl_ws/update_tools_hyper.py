# -*- coding: utf-8 -*-
import sys
import re

f = 'wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_tools.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# For pick
pick_schema_old = """
                        "rotation_dir": types.Schema(
                            type="STRING",
                            enum=["shortest", "cw", "ccw"],
                            description="Optional: force the rotation direction (clockwise 'cw' or counter-clockwise 'ccw') to avoid swinging into adjacent robots. Default is 'shortest'."
                        ),
"""
pick_schema_new = """
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Kinematic movement speed."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover height above the object before descending (meters). Default is 0.1."
                        ),
"""
content = content.replace(pick_schema_old.strip('\n'), pick_schema_new.strip('\n'))

# For place
place_schema_old = """
                        "rotation_dir": types.Schema(
                            type="STRING",
                            enum=["shortest", "cw", "ccw"],
                            description="Optional: force the rotation direction (clockwise 'cw' or counter-clockwise 'ccw') to avoid swinging into adjacent robots. Default is 'shortest'."
                        ),
"""
place_schema_new = """
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Kinematic movement speed."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover height above the placement target before descending (meters). Default is 0.1."
                        ),
"""
content = content.replace(place_schema_old.strip('\n'), place_schema_new.strip('\n'))

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated gemini_tools.py successfully.")

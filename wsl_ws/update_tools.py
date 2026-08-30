# -*- coding: utf-8 -*-
import sys
import re

f = 'wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_tools.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# For pick
pick_schema_old = """
                        "object_label": types.Schema(
                            type="STRING",
                            description="Color and shape label of the object to pick, e.g. 'Red Cube', 'Blue Cylinder'"
                        ),
                    },
                    required=["robot", "object_label"],
"""

pick_schema_new = """
                        "object_label": types.Schema(
                            type="STRING",
                            description="Color and shape label of the object to pick, e.g. 'Red Cube', 'Blue Cylinder'"
                        ),
                        "rotation_dir": types.Schema(
                            type="STRING",
                            enum=["shortest", "cw", "ccw"],
                            description="Optional: force the rotation direction (clockwise 'cw' or counter-clockwise 'ccw') to avoid swinging into adjacent robots. Default is 'shortest'."
                        ),
                    },
                    required=["robot", "object_label"],
"""

content = content.replace(pick_schema_old.strip('\n'), pick_schema_new.strip('\n'))


place_schema_old = """
                        "y": types.Schema(type="NUMBER", description="Target Y coordinate in world frame."),
                    },
                    required=["robot", "x", "y"],
"""

place_schema_new = """
                        "y": types.Schema(type="NUMBER", description="Target Y coordinate in world frame."),
                        "rotation_dir": types.Schema(
                            type="STRING",
                            enum=["shortest", "cw", "ccw"],
                            description="Optional: force the rotation direction (clockwise 'cw' or counter-clockwise 'ccw') to avoid swinging into adjacent robots. Default is 'shortest'."
                        ),
                    },
                    required=["robot", "x", "y"],
"""
content = content.replace(place_schema_old.strip('\n'), place_schema_new.strip('\n'))

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated gemini_tools.py successfully.")

# -*- coding: utf-8 -*-
import sys
import re

f = 'wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# Update dispatch
dispatch_old = """
            elif name == "pick":
                return self._fn_pick(args.get("robot"), args.get("object_label"))
            elif name == "place":
                return self._fn_place(args.get("robot"), args.get("x", 0.0), args.get("y", 0.0))
"""
dispatch_new = """
            elif name == "pick":
                return self._fn_pick(args.get("robot"), args.get("object_label"), args.get("rotation_dir", "shortest"))
            elif name == "place":
                return self._fn_place(args.get("robot"), args.get("x", 0.0), args.get("y", 0.0), args.get("rotation_dir", "shortest"))
"""
content = content.replace(dispatch_old.strip('\n'), dispatch_new.strip('\n'))


fn_pick_old = """
    def _fn_pick(self, robot: str, object_label: str) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": robot,
            "target": object_label
        })
"""
fn_pick_new = """
    def _fn_pick(self, robot: str, object_label: str, rotation_dir: str = 'shortest') -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": robot,
            "target": object_label,
            "rotation_dir": rotation_dir
        })
"""
content = content.replace(fn_pick_old.strip('\n'), fn_pick_new.strip('\n'))


fn_place_old = """
    def _fn_place(self, robot: str, x: float = 0.0, y: float = 0.0) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "place",
            "robot": robot,
            "x": x,
            "y": y
        })
"""
fn_place_new = """
    def _fn_place(self, robot: str, x: float = 0.0, y: float = 0.0, rotation_dir: str = 'shortest') -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "place",
            "robot": robot,
            "x": x,
            "y": y,
            "rotation_dir": rotation_dir
        })
"""
content = content.replace(fn_place_old.strip('\n'), fn_place_new.strip('\n'))

prompt3_old = """
Integrate these precise coordinates into your concurrency-optimized plan.
Provide the FINAL exact X,Y blueprint.
CRITICAL: Keep your text extremely concise. Format your final response starting with "Here is the final execution blueprint:"
"""
prompt3_new = """
Integrate these precise coordinates into your concurrency-optimized plan.
Provide the FINAL exact X,Y blueprint.
CRITICAL: The robots are placed closely together. To avoid swinging collisions, you MUST use the `rotation_dir` parameter ('cw' or 'ccw') when picking and placing! Set FR3_1 (bottom) to 'cw' and FR3_2 (top right) to 'ccw' so they swing outward.
CRITICAL: Keep your text extremely concise. Format your final response starting with "Here is the final execution blueprint:"
"""
content = content.replace(prompt3_old.strip('\n'), prompt3_new.strip('\n'))

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated gemini_robotics_node.py successfully.")

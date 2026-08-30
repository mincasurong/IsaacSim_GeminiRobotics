# -*- coding: utf-8 -*-
import sys
import re

f = 'wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# Replace _fn_pick signature and payload
fn_pick_old = """
    def _fn_pick(self, robot: str, object_label: str, rotation_dir: str = 'shortest') -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": robot,
            "target": object_label,
            "rotation_dir": rotation_dir
        })
"""
fn_pick_new = """
    def _fn_pick(self, robot: str, object_label: str, speed: str = 'normal', approach_height: float = 0.1) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": robot,
            "target": object_label,
            "speed": speed,
            "approach_height": approach_height
        })
"""
content = content.replace(fn_pick_old.strip('\n'), fn_pick_new.strip('\n'))

fn_place_old = """
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
fn_place_new = """
    def _fn_place(self, robot: str, x: float = 0.0, y: float = 0.0, speed: str = 'normal', approach_height: float = 0.1) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "place",
            "robot": robot,
            "x": x,
            "y": y,
            "speed": speed,
            "approach_height": approach_height
        })
"""
content = content.replace(fn_place_old.strip('\n'), fn_place_new.strip('\n'))

# Dispatch update
dispatch_old = """
            elif name == "pick":
                return self._fn_pick(args.get("robot"), args.get("object_label"), args.get("rotation_dir", "shortest"))
            elif name == "place":
                return self._fn_place(args.get("robot"), args.get("x", 0.0), args.get("y", 0.0), args.get("rotation_dir", "shortest"))
"""
dispatch_new = """
            elif name == "pick":
                return self._fn_pick(args.get("robot"), args.get("object_label"), args.get("speed", "normal"), args.get("approach_height", 0.1))
            elif name == "place":
                return self._fn_place(args.get("robot"), args.get("x", 0.0), args.get("y", 0.0), args.get("speed", "normal"), args.get("approach_height", 0.1))
"""
content = content.replace(dispatch_old.strip('\n'), dispatch_new.strip('\n'))


# Brainstorm spatial plan - Turn 3 (Safety) and Turn 4 (Final)
turn3_old = """
            # --- Turn 3: Robotics VLA Finalizes ---
            prompt_3 = f'''
Here is the geometric correction from the Spatial Architect:
{response_2}

Integrate these precise coordinates into your concurrency-optimized plan.
Provide the FINAL exact X,Y blueprint.
CRITICAL: The robots are placed closely together. To avoid swinging collisions, you MUST use the `rotation_dir` parameter ('cw' or 'ccw') when picking and placing! Set FR3_1 (bottom) to 'cw' and FR3_2 (top right) to 'ccw' so they swing outward.
CRITICAL: Keep your text extremely concise. Format your final response starting with "Here is the final execution blueprint:"
'''
            contents = [
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt_1)]),
                genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=response_1)]),
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt_3)])
            ]
            response_3 = stream_chat(
                "Robotics Orchestrator", "🚀", "vla",
                robotics_model, contents,
                genai_types.GenerateContentConfig(temperature=0.1)
            )
            
            return response_3
"""

turn3_new = """
            # --- Turn 3: Safety & Kinematics Verifier ---
            prompt_3 = f'''
You are the Safety & Kinematics Verifier ({architect_model}). Review the combination of the Robotics VLA plan and the Spatial Architect coordinates:

{response_2}

Your job is strictly COLLISION & REACHABILITY verification.
1. The 3 arms are placed very closely together. Identify if their simultaneous pick/place timings will cause mid-air collisions. If so, recommend sequencing (e.g. Robot 1 places, THEN Robot 2 places).
2. Recommend hyperparameter usage: e.g. recommend using `speed="slow"` for delicate places, or higher `approach_height=0.2` if reaching over obstacles.
CRITICAL: Keep your response EXTREMELY concise (2 sentences).
'''
            response_3 = stream_chat(
                "Safety Verifier", "🛡️", "architect",
                architect_model, prompt_3,
                genai_types.GenerateContentConfig(temperature=0.1)
            )

            # --- Turn 4: Robotics VLA Finalizes ---
            prompt_4 = f'''
Here is the safety verification:
{response_3}

Integrate the spatial coordinates and the safety/hyperparameter recommendations into your plan.
Provide the FINAL exact blueprint.
CRITICAL: Keep your text extremely concise. Format your final response starting with "Here is the final execution blueprint:"
'''
            contents = [
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt_1)]),
                genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=response_1)]),
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt_4)])
            ]
            response_4 = stream_chat(
                "Robotics Orchestrator", "🚀", "vla",
                robotics_model, contents,
                genai_types.GenerateContentConfig(temperature=0.1)
            )
            
            return response_4
"""
content = content.replace(turn3_old.strip('\n'), turn3_new.strip('\n'))

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated gemini_robotics_node.py successfully.")

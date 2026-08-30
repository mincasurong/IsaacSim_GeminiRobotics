# -*- coding: utf-8 -*-
import sys

f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

blueprint_func = """
    def _brainstorm_spatial_plan(self, goal_text: str) -> str:
        '''Use a reasoning pass to translate complex shapes into precise coordinates.'''
        from google import genai
        from google.genai import types as genai_types
        
        prompt = f'''
You are the Spatial Architect for a robotic assembly system.
The user wants to: "{goal_text}".

You have 9 blocks available on the tables:
- Block1 (Red Cube), Block2 (Green Cylinder), Block3 (Blue Cube)
- Block4 (Yellow Cylinder), Block5 (Magenta Cube), Block6 (Cyan Cylinder)
- Block7 (Orange Cube), Block8 (Purple Cylinder), Block9 (Lime Cube)

The central target table is at center [X=0.0, Y=0.0]. The physical bounds are roughly X=[-0.15, 0.15], Y=[-0.15, 0.15].
Blocks are about 0.04m wide. 
Your job is to translate the user's goal into exact 2D spatial coordinates (X, Y) and block assignments to achieve this shape (e.g., square, circle, heart, triangle, flat line) on the central table.
Think step-by-step about geometry. 
Return a concise "Spatial Blueprint" detailing the exact X, Y for each block.
'''
        self.get_logger().info("\033[93m[SPATIAL ARCHITECT] Brainstorming spatial blueprint...\033[0m")
        try:
            # Try a reasoning-heavy model first for the architect phase
            try:
                model_to_use = 'gemini-2.5-pro'
                response = self.client.models.generate_content(
                    model=model_to_use,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(temperature=0.1)
                )
            except Exception:
                model_to_use = self.model_name
                response = self.client.models.generate_content(
                    model=model_to_use,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(temperature=0.1)
                )
                
            blueprint = response.text
            self.get_logger().info(f"\033[93m[SPATIAL ARCHITECT] Blueprint generated via {model_to_use}.\\n{blueprint}\033[0m")
            return blueprint
        except Exception as e:
            self.get_logger().error(f"Failed to generate blueprint: {e}")
            return "No blueprint available."

    def _run_vla_orchestration(self, goal_text: str):
"""

content = content.replace('    def _run_vla_orchestration(self, goal_text: str):', blueprint_func)

orchestration_start = """
    def _run_vla_orchestration(self, goal_text: str):
        # 1. Multi-Agent Brainstorming Phase (Spatial Architect)
        blueprint = self._brainstorm_spatial_plan(goal_text)
        
        enhanced_goal = f'''
User Goal: {goal_text}

--- SPATIAL ARCHITECT BLUEPRINT ---
The Spatial Architect agent has brainstormed the following precise coordinate layout for you:
{blueprint}
-----------------------------------
Use this blueprint as a strong recommendation for your 'place' function X,Y coordinates.
'''
        
        system_msg = gemini_prompts.SYSTEM_PROMPT.format(user_goal=enhanced_goal)
"""

content = content.replace(
    '    def _run_vla_orchestration(self, goal_text: str):\n        system_msg = gemini_prompts.SYSTEM_PROMPT.format(user_goal=goal_text)',
    orchestration_start
)

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated gemini_robotics_node.py successfully.")

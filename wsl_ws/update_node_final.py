# -*- coding: utf-8 -*-
import sys
import re

f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# 1. Add publisher
if "self.chat_pub =" not in content:
    content = content.replace(
        "self.action_pub = self.create_publisher(\n            String, '/gemini/action', 10)",
        "self.action_pub = self.create_publisher(\n            String, '/gemini/action', 10)\n        self.chat_pub = self.create_publisher(\n            String, '/gemini/chat_reply', 10)"
    )

# 2. Add brainstorm function before _run_agentic_task
brainstorm_func = """
    def _brainstorm_spatial_plan(self, goal_text: str) -> str:
        '''Use a reasoning pass to translate complex shapes into precise coordinates.'''
        from google import genai
        from google.genai import types as genai_types
        from isaac_ros2_control import gemini_config
        
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

Format your response in a natural, conversational style as if you are brainstorming out loud with the user, followed by the exact X,Y blueprint.
Example structure:
"To build a heart, I'll place the red cube at the bottom tip at [0, -0.08], and then build the lobes using..."
[Then list the exact coordinates]
'''
        self.get_logger().info("\033[93m[SPATIAL ARCHITECT] Brainstorming spatial blueprint...\033[0m")
        try:
            model_to_use = gemini_config.get_planner_model()
            response = self.client.models.generate_content(
                model=model_to_use,
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=0.1)
            )
            blueprint = response.text
            self.get_logger().info(f"\033[93m[SPATIAL ARCHITECT] Blueprint generated via {model_to_use}.\\n{blueprint}\033[0m")
            
            # Send to GUI chat
            chat_msg = String()
            chat_msg.data = f"🧠 **Architect Brainstorming ({model_to_use}):**\\n\\n{blueprint}"
            self.chat_pub.publish(chat_msg)
            
            return blueprint
        except Exception as e:
            self.get_logger().error(f"Failed to generate blueprint: {e}")
            return "No blueprint available."

    def _run_agentic_task(self):
"""

if "_brainstorm_spatial_plan" not in content:
    content = content.replace("    def _run_agentic_task(self):", brainstorm_func)

# 3. Update _run_agentic_task to use the blueprint
run_agentic_target = """        # Initial contents for the conversation
        sys_prompt = gemini_prompts.SYSTEM_PROMPT.format(user_goal=self.user_goal)"""

run_agentic_replacement = """        # Initial contents for the conversation
        
        # 1. Multi-Agent Brainstorming Phase (Spatial Architect)
        blueprint = self._brainstorm_spatial_plan(self.user_goal)
        
        enhanced_goal = f'''
User Goal: {self.user_goal}

--- SPATIAL ARCHITECT BLUEPRINT ---
The Spatial Architect agent has brainstormed the following precise coordinate layout for you:
{blueprint}
-----------------------------------
Use this blueprint as a strong recommendation for your 'place' function X,Y coordinates.
'''
        sys_prompt = gemini_prompts.SYSTEM_PROMPT.format(user_goal=enhanced_goal)"""

if "blueprint = self._brainstorm_spatial_plan" not in content:
    content = content.replace(run_agentic_target, run_agentic_replacement)

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated gemini_robotics_node.py ACTUALLY successfully.")

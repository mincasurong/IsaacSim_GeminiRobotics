# -*- coding: utf-8 -*-
import sys
f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# 1. Add publisher
if "self.chat_pub =" not in content:
    content = content.replace(
        "self.action_pub = self.create_publisher(\n            String, '/gemini/action', 10)",
        "self.action_pub = self.create_publisher(\n            String, '/gemini/action', 10)\n        self.chat_pub = self.create_publisher(\n            String, '/gemini/chat_reply', 10)"
    )

# 2. Update brainstorm function
new_func = """
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

Format your response in a natural, conversational style as if you are brainstorming out loud with the user, followed by the exact X,Y blueprint.
Example structure:
"To build a heart, I'll place the red cube at the bottom tip at [0, -0.08], and then build the lobes using..."
[Then list the exact coordinates]
'''
        self.get_logger().info("\033[93m[SPATIAL ARCHITECT] Brainstorming spatial blueprint...\033[0m")
        try:
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
            
            # Send to GUI chat
            chat_msg = String()
            chat_msg.data = f"🧠 **Architect Brainstorming:**\\n\\n{blueprint}"
            self.chat_pub.publish(chat_msg)
            
            return blueprint
        except Exception as e:
            self.get_logger().error(f"Failed to generate blueprint: {e}")
            return "No blueprint available."
"""

# Replace the existing function
import re
# Regex to replace from 'def _brainstorm_spatial_plan' down to (but not including) 'def _run_vla_orchestration'
pattern = re.compile(r'    def _brainstorm_spatial_plan\(self, goal_text: str\) -> str:.*?    def _run_vla_orchestration', re.DOTALL)
content = pattern.sub(new_func.strip('\n') + '\n\n    def _run_vla_orchestration', content)

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated publisher and brainstorm logic successfully.")

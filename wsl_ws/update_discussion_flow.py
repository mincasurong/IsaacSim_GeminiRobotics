# -*- coding: utf-8 -*-
import sys
import re

f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

new_brainstorm_func = """
    def _brainstorm_spatial_plan(self, goal_text: str) -> str:
        '''Multi-agent brainstorming between Robotics VLA and Spatial Architect.'''
        from google import genai
        from google.genai import types as genai_types
        from isaac_ros2_control import gemini_config
        import time
        
        architect_model = gemini_config.get_planner_model()
        robotics_model = self.model_name
        
        def send_chat(sender, text, emoji):
            msg = String()
            msg.data = f\"\"\"{emoji} **{sender}:**\\n\\n{text}\"\"\"
            self.chat_pub.publish(msg)
            time.sleep(0.5)

        self.get_logger().info("\033[93m[MULTI-AGENT] Starting Brainstorming...\033[0m")
        try:
            # --- Turn 1: Robotics VLA Drafts Initial Plan ---
            prompt_1 = f'''
You are the Robotics VLA Orchestrator ({robotics_model}). The user wants to build: "{goal_text}".

You have 3 robots and 9 blocks available on the source tables:
- Table 1 (FR3_1): Block1 (Red Cube), Block2 (Green Cylinder), Block3 (Blue Cube)
- Table 2 (FR3_2): Block4 (Yellow Cylinder), Block5 (Magenta Cube), Block6 (Cyan Cylinder)
- Table 3 (FR3_3): Block7 (Orange Cube), Block8 (Purple Cylinder), Block9 (Lime Cube)
Central target table is at [X=0.0, Y=0.0].

Draft an initial plan for assigning these blocks to robots.
Your PRIMARY GOAL is to maximize MULTI-ROBOT CONCURRENCY. Assign blocks so that FR3_1, FR3_2, and FR3_3 can pick and place at the same time without sequential bottlenecks.
Do not worry if your geometric math isn't perfect; the Spatial Architect will correct your coordinates in the next step.

Write your response as a natural language proposal to the Spatial Architect.
'''
            response_1 = self.client.models.generate_content(
                model=robotics_model, contents=prompt_1,
                config=genai_types.GenerateContentConfig(temperature=0.2)
            ).text
            send_chat(f"Robotics Orchestrator ({robotics_model})", response_1, "🦾")

            # --- Turn 2: Spatial Architect Corrects Geometry ---
            prompt_2 = f'''
You are the Spatial Architect ({architect_model}). The Robotics VLA has proposed the following concurrency-optimized schedule for building: "{goal_text}".

{response_1}

Your job is strictly GEOMETRIC and MATHEMATICAL CORRECTION. 
Review their proposed plan and provide the exact mathematical 2D spatial coordinates (X, Y) required to actually form the requested shape (e.g., square, circle, heart).
Keep the robot/block assignments they chose to preserve concurrency, but strictly correct the X, Y placement values so the shape is perfect. Blocks are about 0.04m wide.
Keep your response concise and conversational.
'''
            response_2 = self.client.models.generate_content(
                model=architect_model, contents=prompt_2,
                config=genai_types.GenerateContentConfig(temperature=0.1)
            ).text
            send_chat(f"Spatial Architect ({architect_model})", response_2, "📐")

            # --- Turn 3: Robotics VLA Finalizes ---
            prompt_3 = f'''
Here is the geometric correction from the Spatial Architect:
{response_2}

Integrate these precise mathematical coordinates into your original concurrency-optimized plan.
Provide the FINAL exact X,Y blueprint. 
Format your final response starting with "Here is the final execution blueprint:"
'''
            contents = [
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(prompt_1)]),
                genai_types.Content(role="model", parts=[genai_types.Part.from_text(response_1)]),
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(prompt_3)])
            ]
            response_3 = self.client.models.generate_content(
                model=robotics_model, contents=contents,
                config=genai_types.GenerateContentConfig(temperature=0.1)
            ).text
            send_chat(f"Robotics Orchestrator ({robotics_model})", response_3, "🚀")
            
            return response_3

        except Exception as e:
            self.get_logger().error(f"Failed multi-agent brainstorm: {e}")
            return "No blueprint available due to error."
"""

pattern = re.compile(r'    def _brainstorm_spatial_plan\(self, goal_text: str\) -> str:.*?    def _run_agentic_task', re.DOTALL)
if pattern.search(content):
    content = pattern.sub(new_brainstorm_func.strip('\n') + '\n\n    def _run_agentic_task', content)
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
    print("Injected reversed multi-agent brainstorming logic successfully.")
else:
    print("Could not find the function to replace!")

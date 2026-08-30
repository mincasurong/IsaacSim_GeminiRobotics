# -*- coding: utf-8 -*-
import sys
import re

f = 'src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

new_brainstorm_func = """
    def _brainstorm_spatial_plan(self, goal_text: str) -> str:
        '''Multi-agent brainstorming between Spatial Architect and Robotics VLA.'''
        from google import genai
        from google.genai import types as genai_types
        from isaac_ros2_control import gemini_config
        import time
        
        architect_model = gemini_config.get_planner_model()
        robotics_model = self.model_name
        
        def send_chat(sender, text, emoji):
            msg = String()
            msg.data = f"{emoji} **{sender}:**\\n\\n{text}"
            self.chat_pub.publish(msg)
            # Yield slightly to ensure ROS messages arrive in order
            time.sleep(0.5)

        self.get_logger().info("\033[93m[MULTI-AGENT] Starting Brainstorming...\033[0m")
        try:
            # --- Turn 1: Architect Proposes ---
            prompt_1 = f'''
You are the Spatial Architect ({architect_model}). The user wants to: "{goal_text}".

You have 9 blocks available on the source tables:
- Table 1 (FR3_1): Block1 (Red Cube), Block2 (Green Cylinder), Block3 (Blue Cube)
- Table 2 (FR3_2): Block4 (Yellow Cylinder), Block5 (Magenta Cube), Block6 (Cyan Cylinder)
- Table 3 (FR3_3): Block7 (Orange Cube), Block8 (Purple Cylinder), Block9 (Lime Cube)
Central target table is at [X=0.0, Y=0.0].

Design a Spatial Blueprint detailing exact X, Y coordinates for this geometry.
CRITICAL: You must structure your plan to maximize MULTI-ROBOT CONCURRENCY. Do not make a plan that forces sequential execution. Assign blocks so that FR3_1, FR3_2, and FR3_3 can pick and place at the same time whenever possible.

Write your response as a natural language proposal to the Robotics team.
'''
            response_1 = self.client.models.generate_content(
                model=architect_model, contents=prompt_1,
                config=genai_types.GenerateContentConfig(temperature=0.4)
            ).text
            send_chat(f"Spatial Architect ({architect_model})", response_1, "🧠")

            # --- Turn 2: Robotics VLA Critiques ---
            prompt_2 = f'''
You are the Robotics VLA Orchestrator ({robotics_model}). Review this proposed blueprint from the Spatial Architect:

{response_1}

Critique this plan based strictly on:
1. Multi-Robot Parallelism: Are we maximizing simultaneous 'pick' and 'place' actions?
2. Did the architect accidentally create a sequence where robots have to wait for each other unnecessarily?
If it forces sequential moves, firmly suggest how to interleave the robot actions or reassign blocks to different robots for maximum concurrency.
Keep your critique concise, direct, and conversational.
'''
            response_2 = self.client.models.generate_content(
                model=robotics_model, contents=prompt_2,
                config=genai_types.GenerateContentConfig(temperature=0.2)
            ).text
            send_chat(f"Robotics Orchestrator ({robotics_model})", response_2, "🦾")

            # --- Turn 3: Architect Finalizes ---
            prompt_3 = f'''
Here is the feedback from the Robotics Orchestrator:
{response_2}

Revise your blueprint to perfectly incorporate this concurrency feedback.
Provide the FINAL, highly optimized exact X,Y blueprint. 
Format your final response starting with "Here is the final parallel-optimized blueprint:"
'''
            # Pass conversation history so architect knows what was said
            contents = [
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(prompt_1)]),
                genai_types.Content(role="model", parts=[genai_types.Part.from_text(response_1)]),
                genai_types.Content(role="user", parts=[genai_types.Part.from_text(prompt_3)])
            ]
            response_3 = self.client.models.generate_content(
                model=architect_model, contents=contents,
                config=genai_types.GenerateContentConfig(temperature=0.1)
            ).text
            send_chat(f"Spatial Architect ({architect_model})", response_3, "📐")
            
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
    print("Injected multi-agent brainstorming logic successfully.")
else:
    print("Could not find the function to replace!")

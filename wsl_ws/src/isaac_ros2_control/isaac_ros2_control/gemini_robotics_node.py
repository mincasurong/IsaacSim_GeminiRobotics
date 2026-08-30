"""ROS 2 node integrating Gemini Robotics-ER 2 for vision-driven
pick-and-place orchestration using Function Calling.

Subscribes to:
    /overhead_camera/rgb         (sensor_msgs/Image)
    /overhead_camera/depth       (sensor_msgs/Image)
    /overhead_camera/camera_info (sensor_msgs/CameraInfo)
    /gemini/action_result        (std_msgs/String)  <- Results from controller

Publishes:
    /gemini/detected_objects     (std_msgs/String)  -> JSON detections
    /gemini/action               (std_msgs/String)  -> JSON action command

Services:
    /gemini/detect_objects       (std_srvs/Trigger) <- trigger detection
    /gemini/plan_task            (std_srvs/Trigger) <- trigger planning (agentic loop)
    /gemini/describe_scene       (std_srvs/Trigger) <- describe scene
"""

import json
import time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from std_srvs.srv import Trigger
import tf2_ros

try:
    from cv_bridge import CvBridge
except ImportError:
    CvBridge = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

try:
    from isaac_ros2_control import gemini_config
    from isaac_ros2_control import gemini_utils
    from isaac_ros2_control import gemini_prompts
    from isaac_ros2_control import gemini_tools
    from isaac_ros2_control import workspace_state
except ImportError:
    try:
        from . import gemini_config
        from . import gemini_utils
        from . import gemini_prompts
        from . import gemini_tools
        from . import workspace_state
    except ImportError:
        import gemini_config
        import gemini_utils
        import gemini_prompts
        import gemini_tools
        import workspace_state


class GeminiRoboticsNode(Node):
    """ROS 2 node that uses Gemini Robotics-ER VLM for scene understanding
    and agentic task orchestration via Function Calling."""

    def __init__(self):
        super().__init__('gemini_robotics_node')

        # Parameters
        self.declare_parameter('env_file', '')
        self.declare_parameter('detection_interval', 0.0)  # 0 = manual only

        env_file = self.get_parameter('env_file').get_parameter_value().string_value
        env_path = env_file if env_file else None

        # Gemini API Client
        if genai is None:
            self.get_logger().error(
                'google-genai package not installed. '
                'Install with: pip install google-genai'
            )
            self.client = None
        else:
            api_key = gemini_config.get_api_key(env_path)
            if not api_key:
                self.get_logger().error(
                    'No Gemini API key found. Set LLM_API_KEY in .env '
                    'or GEMINI_API_KEY environment variable.'
                )
                self.client = None
            else:
                self.client = genai.Client(api_key=api_key)
                self.get_logger().info('Gemini API client initialized.')

        self.model_name = gemini_config.get_model_name(env_path)
        self.get_logger().info(f'Using model: {self.model_name}')

        # CV Bridge
        if CvBridge is not None:
            self.bridge = CvBridge()
        else:
            self.bridge = None
            self.get_logger().warn('cv_bridge not available. Image conversion disabled.')

        # State
        self.latest_rgb = None
        self.latest_depth = None
        self.camera_intrinsics = None
        self.last_detections = None
        
        self.action_results = {}
        self.user_goal = "Your ultimate goal is to build a single, stable 9-layer tower on the central target table using ALL 9 available objects."
        self.is_running = False
        self.cancel_current_task = False
        
        # TF2 for querying block positions from Isaac Sim
        self.tf_buffer = tf2_ros.Buffer(node=self)
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Known robot base positions in world frame (from three_robot_tower.py)
        self.robot_bases = {
            'FR3_1': np.array([0.0, -0.45]),
            'FR3_2': np.array([0.3897, 0.225]),
            'FR3_3': np.array([-0.3897, 0.225]),
        }
        
        self.workspace_state = workspace_state.WorkspaceState()
        
    # Callback Groups
        from rclpy.callback_groups import ReentrantCallbackGroup
        self.cb_group = ReentrantCallbackGroup()

        # Subscribers
        self.rgb_sub = self.create_subscription(
            Image, '/overhead_camera/rgb', self._rgb_callback, 10, callback_group=self.cb_group)
        self.depth_sub = self.create_subscription(
            Image, '/overhead_camera/depth', self._depth_callback, 10, callback_group=self.cb_group)
        self.info_sub = self.create_subscription(
            CameraInfo, '/overhead_camera/camera_info', self._info_callback, 10, callback_group=self.cb_group)
            
        self.result_sub = self.create_subscription(
            String, '/gemini/action_result', self._result_callback, 10, callback_group=self.cb_group)
        self.custom_goal_sub = self.create_subscription(
            String, '/gemini/custom_goal', self._custom_goal_callback, 10, callback_group=self.cb_group)

        # Publishers
        self.detection_pub = self.create_publisher(
            String, '/gemini/detected_objects', 10)
        self.action_pub = self.create_publisher(
            String, '/gemini/action', 10)
        self.chat_pub = self.create_publisher(
            String, '/gemini/chat_reply', 10)

        # Services
        self.detect_srv = self.create_service(
            Trigger, '/gemini/detect_objects', self._detect_objects_cb, callback_group=self.cb_group)
        self.plan_srv = self.create_service(
            Trigger, '/gemini/plan_task', self._plan_task_cb, callback_group=self.cb_group)
        self.describe_srv = self.create_service(
            Trigger, '/gemini/describe_scene', self._describe_scene_cb, callback_group=self.cb_group)

        # Optional periodic detection
        interval = self.get_parameter('detection_interval').get_parameter_value().double_value
        if interval > 0:
            self.create_timer(interval, self._periodic_detect, callback_group=self.cb_group)

        self.get_logger().info(
            'Gemini Robotics Node started (Function Calling mode). '
            'Call /gemini/plan_task to begin the agentic loop.'
        )

    # Camera Result Callbacks

    def _rgb_callback(self, msg):
        if self.bridge is not None:
            try:
                self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            except Exception as e:
                self.get_logger().warn(f'RGB conversion failed: {e}')

    def _depth_callback(self, msg):
        if self.bridge is not None:
            try:
                self.latest_depth = self.bridge.imgmsg_to_cv2(msg, 'passthrough')
            except Exception as e:
                self.get_logger().warn(f'Depth conversion failed: {e}')

    def _info_callback(self, msg):
        import numpy as np
        self.camera_intrinsics = np.array(msg.k).reshape(3, 3)

    def _result_callback(self, msg):
        try:
            res = json.loads(msg.data)
            robot_id = str(res.get("robot_id", ""))
            if robot_id:
                self.action_results[robot_id] = res
            else:
                self.action_results["global"] = res
        except Exception as e:
            self.get_logger().error(f"Failed to parse action result: {e}")

    def _custom_goal_callback(self, msg):
        self.user_goal = msg.data
        self.get_logger().info(f"\033[92m[PROMPT] Received custom goal: {self.user_goal}\033[0m")
        
        # Automatically trigger planning
        import threading
        def trigger_plan():
            from std_srvs.srv import Trigger
            req = Trigger.Request()
            res = Trigger.Response()
            self._plan_task_cb(req, res)
        
        threading.Thread(target=trigger_plan, daemon=True).start()

    # Service Callbacks

    def _call_gemini(self, image_bytes, prompt, thinking_budget=0):
        """Call Gemini API with an image and a prompt."""
        if self.client is None:
            raise RuntimeError('Gemini API client is not initialized.')

        config_kwargs = {'temperature': 1.0}
        if thinking_budget >= 0:
            config_kwargs['thinking_config'] = genai_types.ThinkingConfig(
                thinking_budget=thinking_budget
            )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                genai_types.Part.from_bytes(
                    data=image_bytes, mime_type='image/png'),
                prompt,
            ],
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
        return response.text

    # Service Handlers

    def _detect_objects_cb(self, request, response):
        """Service: detect objects in the latest camera frame."""
        if genai is None or self.client is None:
            response.success = False
            response.message = "google-genai client is not initialized. Run: pip install --break-system-packages google-genai"
            return response

        if self.latest_rgb is None:
            import time
            for _ in range(20):
                if self.latest_rgb is not None:
                    break
                time.sleep(0.1)

        if self.latest_rgb is None:
            response.success = False
            response.message = 'No camera frame available yet. Is Isaac Sim PLAYING?'
            return response

        try:
            result = self._fn_detect_objects()
            response.success = True
            response.message = f"Detected {len(result)} objects."
        except Exception as e:
            response.success = False
            response.message = f'Detection failed: {e}'
            self.get_logger().error(response.message)
        return response

    def _plan_task_cb(self, request, response):
        """Service: Trigger the agentic building loop."""
        if genai is None or genai_types is None or self.client is None:
            response.success = False
            response.message = (
                "google-genai is not initialized. Please install it in WSL2 with: "
                "'pip install --break-system-packages google-genai' and verify LLM_API_KEY in private/.env"
            )
            self.get_logger().error(response.message)
            return response

        if self.latest_rgb is None:
            # Wait up to 2 seconds for the first frame
            import time
            for _ in range(20):
                if self.latest_rgb is not None:
                    break
                time.sleep(0.1)

        if self.latest_rgb is None:
            response.success = False
            response.message = 'No camera frame available yet. Is Isaac Sim PLAYING (started)?'
            return response

        if self.is_running:
            self.get_logger().warn("\033[93m[WARN] A task is already running. Cancelling it...\033[0m")
            self.cancel_current_task = True
            import time
            while self.is_running:
                time.sleep(0.1)
            self.cancel_current_task = False

        self.is_running = True
        try:
            self._run_agentic_task()
            response.success = True
            response.message = "Agentic loop completed."
        except Exception as e:
            import traceback
            response.success = False
            response.message = f'Planning loop failed: {e}'
            self.get_logger().error(response.message)
            self.get_logger().error(traceback.format_exc())
        finally:
            self.is_running = False
            self.cancel_current_task = False
        return response

    def _describe_scene_cb(self, request, response):
        """Service: describe the current scene in natural language."""
        if genai is None or self.client is None:
            response.success = False
            response.message = "google-genai client is not initialized. Run: pip install --break-system-packages google-genai"
            return response
        if self.latest_rgb is None:
            import time
            for _ in range(20):
                if self.latest_rgb is not None:
                    break
                time.sleep(0.1)
                
        if self.latest_rgb is None:
            response.success = False
            response.message = 'No camera frame available yet. Is Isaac Sim PLAYING?'
            return response

        try:
            image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
            description = self._call_gemini(
                image_bytes, gemini_prompts.DESCRIBE_SCENE_PROMPT,
                thinking_budget=512)

            response.success = True
            response.message = description
            self.get_logger().info(f'Scene description: {description[:200]}...')
        except Exception as e:
            response.success = False
            response.message = f'Scene description failed: {e}'
        return response

    def _periodic_detect(self):
        """Timer callback for periodic automatic detection."""
        if self.latest_rgb is None or self.client is None:
            return
        try:
            self._fn_detect_objects()
        except Exception as e:
            self.get_logger().warn(f'Periodic detection failed: {e}')

    # Agentic Loop Tool Execution


    def _brainstorm_spatial_plan(self, goal_text: str, image_bytes: bytes = None) -> str:
        """Multi-agent discussion between Gemini Robotics-ER and Gemini Flash Spatial Architect."""
        from google.genai import types as genai_types
        from isaac_ros2_control import gemini_config
        import time
        import uuid
        import json
        
        architect_model = gemini_config.get_planner_model()
        robotics_model = self.model_name
        
        def stream_chat(sender, emoji, role, model_name, req_contents, req_config):
            msg_id = str(uuid.uuid4())
            # Send initial header metadata
            header = {
                "id": msg_id, 
                "text": "", 
                "senderName": f"{sender} ({model_name})", 
                "emoji": emoji, 
                "role": role
            }
            msg = String()
            msg.data = json.dumps(header)
            self.chat_pub.publish(msg)
            
            full_text = ""
            try:
                response = self.client.models.generate_content_stream(
                    model=model_name,
                    contents=req_contents,
                    config=req_config
                )
                for chunk in response:
                    if chunk.text:
                        chunk_msg = String()
                        chunk_msg.data = json.dumps({"id": msg_id, "text": chunk.text})
                        self.chat_pub.publish(chunk_msg)
                        full_text += chunk.text
                        time.sleep(0.01)  # small buffer for ROS 2 pub
            except Exception as e:
                self.get_logger().error(f"Streaming error: {e}")
                
            return full_text

        self.get_logger().info("\033[93m[MULTI-AGENT] Starting Brainstorming...\033[0m")
        try:
            # Query TF for block proximity data
            proximity_text = ""
            block_positions = self._query_block_positions()
            if block_positions:
                lines = []
                for robot_name, base_xy in self.robot_bases.items():
                    dists = []
                    for block_name, pos in block_positions.items():
                        d = np.hypot(pos[0] - base_xy[0], pos[1] - base_xy[1])
                        dists.append((block_name, pos, d))
                    dists.sort(key=lambda x: x[2])
                    ranked = ", ".join([f"{b}({round(d,2)}m)" for b, _, d in dists[:5]])
                    lines.append(f"  {robot_name}: nearest blocks → {ranked}")
                proximity_text = "\n".join(lines)

            # --- Turn 1: Robotics VLA Drafts Initial Plan ---
            prompt_1 = f'''
You are the Robotics VLA Orchestrator ({robotics_model}). The user wants to build: "{goal_text}".

Workspace layout:
- FR3_1 (Bottom arm): operates on Source Table 1 ([0.0, -1.05]) and the Central Target Table ([0.0, 0.0])
- FR3_2 (Top-right arm): operates on Source Table 2 ([0.909, 0.525]) and the Central Target Table ([0.0, 0.0])
- FR3_3 (Top-left arm): operates on Source Table 3 ([-0.909, 0.525]) and the Central Target Table ([0.0, 0.0])

MEASURED block distances from each robot base (pick CLOSEST blocks first!):
{proximity_text if proximity_text else "(TF data not yet available — use visual proximity from the camera image)"}

Draft an initial plan assigning tasks to the robots to achieve the user's goal.
1. Proximity Rule: ALWAYS pick the block with the SHORTEST distance from the robot base first. The distances above are measured in meters — lower = closer = pick first.
2. Concurrency: Maximize MULTI-ROBOT CONCURRENCY so multiple arms can pick/place simultaneously.
CRITICAL: Keep your response EXTREMELY concise (under 2-3 sentences).
'''
            req_1 = [
                genai_types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
                genai_types.Part.from_text(text=prompt_1)
            ] if image_bytes else prompt_1

            response_1 = stream_chat(
                "Robotics Orchestrator", "🦾", "vla",
                robotics_model, req_1,
                genai_types.GenerateContentConfig(temperature=0.2)
            )
            
            is_complex = any(kw in goal_text.lower() for kw in ['tower', 'layer', 'stack', 'build', 'pattern', 'replan', 'arrange'])
            
            if is_complex:
                # --- Turn 2: Spatial Architect Corrects Geometry ---
                prompt_2 = f'''
You are the Spatial Architect ({architect_model}). The Robotics VLA has proposed the following schedule for building: "{goal_text}".

{response_1}

Your job is strictly GEOMETRIC and MATHEMATICAL CORRECTION.
Do NOT try to guess raw absolute (X,Y) coordinates for complex shapes! Instead, use Relative Placement.
1. First, draw an ASCII top-down grid of the desired shape using `[]` for blocks and `.` for empty space.
2. Second, pick ONE block to be the central anchor placed at (0, 0).
3. Third, map all other blocks relative to that anchor using the relation keywords: `on_top_of`, `left_of`, `right_of`, `front_of`, `back_of`.

CRITICAL: Keep your response EXTREMELY concise. Draw the ASCII grid, then list the exact relative placement mappings.
'''
                response_2 = stream_chat(
                    "Spatial Architect", "📐", "architect",
                    architect_model, prompt_2,
                    genai_types.GenerateContentConfig(temperature=0.1)
                )

                # --- Turn 3: Safety & Kinematics Verifier ---
                prompt_3 = f'''
You are the Safety & Kinematics Verifier ({architect_model}). Review the proposed multi-robot execution plan:

{response_2}

Analyze safety, trajectory interference, and kinematics:
1. Proximity & Reachability: Ensure arms pick closest objects on their table first to avoid reaching near singularity boundaries.
2. Concurrency & Collision Check: If multiple arms place at the center table simultaneously, specify explicit execution order (e.g., dispatch non-conflicting picks concurrently, but serialize center placements).
3. Dynamic Hyperparameters:
   - `speed`: select 'fast' for unobstructed initial movements, 'normal' for standard transport, and 'slow' for high-precision placement or higher tower layers.
   - `approach_height`: default is 0.1m; increase to 0.15m - 0.25m when stacking atop existing blocks or clearing surrounding objects.

CRITICAL: Provide clear, actionable safety directives and hyperparameter choices in under 2-3 sentences.
'''
                response_3 = stream_chat(
                    "Safety Verifier", "🛡️", "architect",
                    architect_model, prompt_3,
                    genai_types.GenerateContentConfig(temperature=0.1)
                )

                # --- Turn 4: Robotics VLA Finalizes ---
                prompt_4 = f'''
Here is the safety and kinematic review (including relative placement mappings):
{response_3}

Finalize the plan by integrating the relative placement strategy and the safety/hyperparameter directives (speed, approach_height, concurrency order).
Make sure to emphasize that the agent MUST use the `place_relative` tool for all blocks other than the anchor block, rather than guessing absolute (X,Y) coordinates.
Provide the FINAL exact blueprint.
CRITICAL: Keep your text concise. Format your final response starting with "Here is the final execution blueprint:"
'''
            else:
                prompt_4 = f'''
Based on your initial plan, finalize the execution blueprint. 
Since this is a simple task, no complex spatial coordinates or safety overrides are needed. Just proceed.
CRITICAL: Keep your text concise. Format your final response starting with "Here is the final execution blueprint:"
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

        except Exception as e:
            self.get_logger().error(f"Failed multi-agent brainstorm: {e}")
            return "No blueprint available due to error."

    def _run_agentic_task(self):

        """Agentic loop: Gemini calls functions, we execute them."""
        self.get_logger().info("\033[94m[AGENT] Starting Agentic Loop...\033[0m")
        
        image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        
        # Initial contents for the conversation
        
        # 1. Multi-Agent Brainstorming Phase (Spatial Architect)
        blueprint = self._brainstorm_spatial_plan(self.user_goal, image_bytes)
        
        enhanced_goal = f'''
User Goal: {self.user_goal}

--- SPATIAL ARCHITECT BLUEPRINT ---
The Spatial Architect agent has brainstormed the following precise coordinate layout for you:
{blueprint}
-----------------------------------
Use this blueprint as a strong recommendation for your 'place' function X,Y coordinates.
'''
        sys_prompt = gemini_prompts.SYSTEM_PROMPT.format(user_goal=enhanced_goal)
        contents = [
            genai_types.Content(
                role="user",
                parts=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
                    genai_types.Part.from_text(text=sys_prompt)
                ]
            )
        ]
        max_turns = 45
        placement_count = 0
        
        for turn in range(max_turns):
            if self.cancel_current_task:
                self.get_logger().warn("\033[93m[WARN] Aborting current agentic loop due to cancellation request!\033[0m")
                break
                
            self.get_logger().info(f"\033[94m[AGENT] Agentic Turn {turn+1}/{max_turns}\033[0m")
            
            # Periodically inject fresh visual context (every 3 turns)
            if turn > 0 and turn % 3 == 0 and self.latest_rgb is not None:
                self.get_logger().info("\033[96m[VISION] Injecting fresh camera frame into context...\033[0m")
                fresh_image = gemini_utils.encode_image_to_bytes(self.latest_rgb)
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=[
                            genai_types.Part.from_bytes(data=fresh_image, mime_type='image/png'),
                            genai_types.Part.from_text(text="[SYSTEM AUTO-REFRESH] Here is the latest overhead camera view.")
                        ]
                    )
                )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    temperature=0.0,
                    tools=gemini_tools.ROBOT_TOOLS,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=1024),
                ),
            )
            
            if not response.candidates:
                self.get_logger().error("No candidates returned from Gemini.")
                break
                
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                self.get_logger().error("Empty content returned from Gemini.")
                break
                
            part = candidate.content.parts[0]
            
            # If there are function calls, execute them in parallel
            func_parts = [p for p in candidate.content.parts if p.function_call]
            if func_parts:
                self.get_logger().debug(f"\033[95m[GEMINI] Issued {len(func_parts)} parallel function calls.\033[0m")
                contents.append(candidate.content)
                
                import concurrent.futures
                response_parts = []
                replan_triggered = False
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(func_parts)) as executor:
                    futures = {
                        executor.submit(self._execute_function, p.function_call.name, p.function_call.args): p.function_call
                        for p in func_parts
                    }
                    
                    for future in concurrent.futures.as_completed(futures):
                        fc = futures[future]
                        self.get_logger().info(f"\033[96m[TOOL] Executing: {fc.name} with args {fc.args}\033[0m")
                        try:
                            res = future.result()
                            if fc.name == "place" and res.get("success", False):
                                placement_count += 1
                            if fc.name == "replan":
                                replan_triggered = True
                        except Exception as e:
                            import traceback
                            self.get_logger().error(f"Function {fc.name} failed with exception: {e}")
                            self.get_logger().error(traceback.format_exc())
                            res = {"error": str(e)}
                            
                        response_parts.append(
                            genai_types.Part.from_function_response(
                                name=fc.name,
                                response=res
                            )
                        )
                        
                # Append the function responses
                contents.append(
                    genai_types.Content(
                        role="user",
                        parts=response_parts
                    )
                )
                
                if replan_triggered:
                    self.get_logger().info("\033[93m[REPLAN] Initiating mid-task brainstorm...\033[0m")
                    fresh_image = gemini_utils.encode_image_to_bytes(self.latest_rgb)
                    new_blueprint = self._brainstorm_spatial_plan("REPLAN AND RECOVER. " + self.user_goal, fresh_image)
                    contents.append(
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part.from_text(text=f"[SYSTEM REPLAN RESULTS] The Spatial Architect provides a new blueprint:\n{new_blueprint}")
                            ]
                        )
                    )
                    
                # Auto Verify after 3 placements
                if placement_count >= 3:
                    self.get_logger().info("\033[96m[AUTO-VERIFY] 3 placements completed. Triggering auto-verification...\033[0m")
                    placement_count = 0
                    verify_res = self._fn_verify_tower()
                    if not verify_res.get("success", True):
                         contents.append(
                            genai_types.Content(
                                role="user",
                                parts=[
                                    genai_types.Part.from_text(text=f"[SYSTEM WARNING] Auto-verification failed! Issues: {verify_res.get('issues')}. Please adapt your plan.")
                                ]
                            )
                        )
            else:
                # Text response (task complete or final output)
                text_parts = []
                for p in candidate.content.parts:
                    if getattr(p, 'text', None):
                        text_parts.append(p.text)
                
                final_text = " ".join(text_parts) if text_parts else "No text response."
                self.get_logger().info(f"\033[92m[DONE] Agent finished: {final_text}\033[0m")
                break

    def _execute_function(self, name: str, args: dict) -> dict:
        """Dispatch function calls to actual robot controllers."""
        try:
            result = None
            if name == "detect_objects":
                result = {"objects": self._fn_detect_objects()}
            elif name == "pick":
                result = self._fn_pick(args.get("robot"), args.get("object_label"), args.get("speed", "normal"), args.get("approach_height", 0.1))
                # Auto-retry / enriched error context on pick failure
                if not result.get("success", True):
                    self.get_logger().warn(f"Pick failed. Enclosing fresh workspace status.")
                    self.workspace_state.update_from_tf(self.tf_buffer)
                    status = self.workspace_state.get_summary()
                    result["error_context"] = f"Pick failed. Current workspace status: {json.dumps(status)}. Suggest calling replan or try an alternative."
            elif name == "place":
                result = self._fn_place(args.get("robot"), args.get("x", 0.0), args.get("y", 0.0), args.get("speed", "normal"), args.get("approach_height", 0.1))
            elif name == "place_relative":
                result = self._fn_place_relative(args.get("robot"), args.get("anchor_block"), args.get("relation"), args.get("speed", "normal"), args.get("approach_height", 0.1))
            elif name == "verify_tower":
                result = self._fn_verify_tower()
            elif name == "go_home":
                result = self._fn_go_home(args.get("robot"))
            elif name == "get_workspace_status":
                result = self._fn_get_status()
            elif name == "replan":
                result = self._fn_replan()
            else:
                result = {"error": f"Unknown function: {name}"}
                
            # Log action history
            if name in ["pick", "place", "go_home"]:
                self.workspace_state.record_action(f"{name} {args}", result.get("success", True), result.get("message", ""))
                
            return result
        except Exception as e:
            self.get_logger().error(f"Error executing {name}: {e}")
            self.workspace_state.record_action(f"{name} {args}", False, str(e))
            return {"error": str(e)}

    def _wait_for_action_complete(self, robot_id: str, timeout=30.0):
        """Wait for the controller to publish a result for a specific robot."""
        self.action_results.pop(robot_id, None)
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.cancel_current_task:
                return {"success": False, "message": "Action aborted due to task cancellation."}
            time.sleep(0.1)  # Yield to the MultiThreadedExecutor
            if robot_id in self.action_results:
                return self.action_results.pop(robot_id)
        return {"success": False, "message": f"Timeout waiting for controller for robot {robot_id}"}


    # Concrete Primitive Implementations

    def _fn_detect_objects(self) -> list:
        image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        result_text = self._call_gemini(
            image_bytes, gemini_prompts.DETECT_BLOCKS_PROMPT, thinking_budget=0)
        detections = gemini_utils.parse_gemini_response(result_text)
        self.last_detections = detections

        # Enrich detections with TF-based proximity data
        block_positions = self._query_block_positions()
        if block_positions:
            # Build a proximity summary for each robot
            proximity_info = []
            for robot_name, base_xy in self.robot_bases.items():
                distances = []
                for block_name, pos in block_positions.items():
                    d = np.hypot(pos[0] - base_xy[0], pos[1] - base_xy[1])
                    distances.append({"block": block_name, "world_xy": [round(pos[0], 3), round(pos[1], 3)], "distance_m": round(d, 3)})
                distances.sort(key=lambda x: x["distance_m"])
                proximity_info.append({"robot": robot_name, "blocks_by_distance": distances})
            
            # Attach proximity data to the detection result
            return {"visual_detections": detections, "proximity": proximity_info}

        msg = String()
        msg.data = json.dumps(detections)
        self.detection_pub.publish(msg)
        return detections

    def _query_block_positions(self) -> dict:
        """Query TF for world-frame XY positions of all 9 blocks."""
        positions = {}
        for i in range(1, 10):
            block_name = f"Block{i}"
            try:
                trans = self.tf_buffer.lookup_transform(
                    'world', block_name, rclpy.time.Time(), timeout=Duration(seconds=0.1))
                x = trans.transform.translation.x
                y = trans.transform.translation.y
                positions[block_name] = (x, y)
            except Exception:
                pass  # Block may not exist or TF not yet available
        return positions

    def _fn_pick(self, robot: str, object_label: str, speed: str = 'normal', approach_height: float = 0.1) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": robot,
            "target": object_label,
            "speed": speed,
            "approach_height": approach_height
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(robot, timeout=25.0)

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
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(robot, timeout=25.0)

    def _fn_place_relative(self, robot: str, anchor_block: str, relation: str, speed: str = 'normal', approach_height: float = 0.1) -> dict:
        """Resolve a relative placement request into absolute coordinates via TF."""
        try:
            # Clean block name (e.g., 'Red Cube' -> 'Block1')
            block_key = gemini_utils.resolve_block_key(anchor_block)
            if not block_key:
                return {"success": False, "message": f"Could not resolve anchor block name: {anchor_block}"}
            
            # Lookup anchor in TF
            transform = self.tf_buffer.lookup_transform('world', block_key, rclpy.time.Time())
            anchor_x = transform.transform.translation.x
            anchor_y = transform.transform.translation.y
            
            # Apply offset
            block_size = 0.045 # 4.5cm block width + tolerance
            target_x, target_y = anchor_x, anchor_y
            
            if relation == "left_of":
                target_y += block_size
            elif relation == "right_of":
                target_y -= block_size
            elif relation == "front_of":
                target_x += block_size
            elif relation == "back_of":
                target_x -= block_size
            elif relation == "on_top_of":
                pass # Same X, Y. The multi_robot_controller dynamically computes Z.
            else:
                return {"success": False, "message": f"Unknown relation: {relation}"}
                
            self.get_logger().info(f"\033[96m[TOOL] place_relative resolved {relation} {anchor_block} to X:{target_x:.3f}, Y:{target_y:.3f}\033[0m")
            return self._fn_place(robot, float(target_x), float(target_y), speed, approach_height)
        except Exception as e:
            self.get_logger().error(f"Error in place_relative: {e}")
            return {"success": False, "message": f"TF lookup failed for {anchor_block}: {e}"}


    def _fn_go_home(self, robot: str) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "go_home",
            "robot": robot,
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(robot, timeout=20.0)

    def _fn_verify_tower(self) -> dict:
        # Give physics a moment to settle
        import time
        time.sleep(1.0)
        
        msg = String()
        msg.data = json.dumps({
            "action": "verify_tower"
        })
        self.action_pub.publish(msg)
        
        res = self._wait_for_action_complete("global", timeout=10.0)
        if not res.get("success", False):
            return {"success": False, "issues": "Failed to drive robots out of the way to verify."}

        # Take new picture
        image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        verify_response = self._call_gemini(
            image_bytes, 
            gemini_prompts.VERIFY_PLACEMENT_PROMPT,
            thinking_budget=512
        )
        try:
            return gemini_utils.parse_gemini_response(verify_response)
        except Exception as e:
            return {"success": False, "issues": f"Failed to parse verify response: {e}"}

    def _fn_get_status(self) -> dict:
        self.workspace_state.update_from_tf(self.tf_buffer)
        return self.workspace_state.get_summary()

    def _fn_replan(self) -> dict:
        """Trigger a fresh brainstorm."""
        self.get_logger().warn("Replanning requested by agent.")
        image_bytes = None
        if self.latest_rgb is not None:
            image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        
        # We return a special dict that _execute_function handles
        return {"action": "replan_requested"}


def main(args=None):
    rclpy.init(args=args)
    node = GeminiRoboticsNode()
    from rclpy.executors import MultiThreadedExecutor
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()


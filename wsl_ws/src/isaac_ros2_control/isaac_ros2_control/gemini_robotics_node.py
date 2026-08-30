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
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from std_srvs.srv import Trigger

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
except ImportError:
    try:
        from . import gemini_config
        from . import gemini_utils
        from . import gemini_prompts
        from . import gemini_tools
    except ImportError:
        import gemini_config
        import gemini_utils
        import gemini_prompts
        import gemini_tools


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

    def _run_agentic_task(self):
        """Agentic loop: Gemini calls functions, we execute them."""
        self.get_logger().info("\033[94m[AGENT] Starting Agentic Loop...\033[0m")
        
        image_bytes = gemini_utils.encode_image_to_bytes(self.latest_rgb)
        
        # Initial contents for the conversation
        sys_prompt = gemini_prompts.SYSTEM_PROMPT.format(user_goal=self.user_goal)
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
        for turn in range(max_turns):
            if self.cancel_current_task:
                self.get_logger().warn("\033[93m[WARN] Aborting current agentic loop due to cancellation request!\033[0m")
                break
                
            self.get_logger().info(f"\033[94m[AGENT] Agentic Turn {turn+1}/{max_turns}\033[0m")
            
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
            if name == "detect_objects":
                return {"objects": self._fn_detect_objects()}
            elif name == "pick":
                return self._fn_pick(args.get("robot"), args.get("object_label"))
            elif name == "place":
                return self._fn_place(args.get("robot"), args.get("x", 0.0), args.get("y", 0.0))
            elif name == "verify_tower":
                return self._fn_verify_tower()
            elif name == "go_home":
                return self._fn_go_home(args.get("robot"))
            elif name == "get_workspace_status":
                return self._fn_get_status()
            else:
                return {"error": f"Unknown function: {name}"}
        except Exception as e:
            self.get_logger().error(f"Error executing {name}: {e}")
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

        msg = String()
        msg.data = json.dumps(detections)
        self.detection_pub.publish(msg)
        return detections

    def _fn_pick(self, robot: str, object_label: str) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "pick",
            "robot": robot,
            "target": object_label,
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(robot, timeout=25.0)

    def _fn_place(self, robot: str, x: float = 0.0, y: float = 0.0) -> dict:
        msg = String()
        msg.data = json.dumps({
            "action": "place",
            "robot": robot,
            "x": x,
            "y": y
        })
        self.action_pub.publish(msg)
        return self._wait_for_action_complete(robot, timeout=25.0)

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
        return {"status": "Workspace operational. Proceed with task."}


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


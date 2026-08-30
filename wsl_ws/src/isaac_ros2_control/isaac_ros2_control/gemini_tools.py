"""Tool definitions for Gemini Robotics-ER Function Calling."""

try:
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    types = None
    GENAI_AVAILABLE = False


def get_robot_tools():
    """Construct Google GenAI Tool schema for robot function calling."""
    if not GENAI_AVAILABLE or types is None:
        return []

    return [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="detect_objects",
                description="Take an overhead photo and detect all colored blocks/cylinders on the table. Returns list of objects with positions.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="pick",
                description="Command a robot arm to pick up a specific object from the table.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robot": types.Schema(
                            type="STRING",
                            enum=["FR3_1", "FR3_2", "FR3_3"],
                            description="Which robot arm to use. FR3_1 covers bottom quadrant, FR3_2 covers top-right, FR3_3 covers top-left."
                        ),
                        "object_label": types.Schema(
                            type="STRING",
                            description="Color and shape label of the object to pick, e.g. 'Red Cube', 'Blue Cylinder'"
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Kinematic movement speed."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover height above the object before descending (meters). Default is 0.1."
                        ),
                    },
                    required=["robot", "object_label"],
                ),
            ),
            types.FunctionDeclaration(
                name="place",
                description="Place the currently held object at the specified absolute world X, Y coordinates. You can place objects anywhere in the workspace (central table, floor, source trays, etc). Z-height will be automatically calculated to stack on top of objects at that location if any.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robot": types.Schema(
                            type="STRING",
                            enum=["FR3_1", "FR3_2", "FR3_3"],
                            description="Which robot arm is holding the object."
                        ),
                        "x": types.Schema(type="NUMBER", description="Target X coordinate in world frame."),
                        "y": types.Schema(type="NUMBER", description="Target Y coordinate in world frame."),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Kinematic movement speed."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover height above the object before descending (meters). Default is 0.1."
                        ),
                    },
                    required=["robot", "x", "y"],
                ),
            ),
            types.FunctionDeclaration(
                name="place_relative",
                description="Place the currently held object relative to an existing block on the central table (e.g. on top, to the left, right, front, back). The system will automatically calculate the correct coordinates based on the anchor block's current position.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robot": types.Schema(
                            type="STRING",
                            enum=["FR3_1", "FR3_2", "FR3_3"],
                            description="Which robot arm is holding the object."
                        ),
                        "anchor_block": types.Schema(
                            type="STRING", 
                            description="The name of the block already placed on the table to use as a reference point (e.g., 'Block1', 'Red Cube')."
                        ),
                        "relation": types.Schema(
                            type="STRING",
                            enum=["on_top_of", "left_of", "right_of", "front_of", "back_of"],
                            description="Where to place the object relative to the anchor block. 'on_top_of' stacks it. 'left_of'/etc places it adjacently."
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Kinematic movement speed."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover height above the object before descending (meters). Default is 0.1."
                        ),
                    },
                    required=["robot", "anchor_block", "relation"],
                ),
            ),
            types.FunctionDeclaration(
                name="verify_tower",
                description="Take a new overhead photo and verify the current workspace state. Returns assessment of the shapes/towers and any issues.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="go_home",
                description="Send a robot arm back to its home/rest position.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robot": types.Schema(
                            type="STRING",
                            enum=["FR3_1", "FR3_2", "FR3_3"],
                            description="Which robot arm to send home."
                        ),
                    },
                    required=["robot"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_workspace_status",
                description="Get the current state of all robots and objects. Returns which robots are idle/busy and what objects remain.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="replan",
                description="Trigger a full re-evaluation of the workspace via a multi-agent brainstorm. Use this if the environment has drastically changed or if previous plans are repeatedly failing.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={},
                ),
            ),
        ]),
    ]


ROBOT_TOOLS = get_robot_tools()


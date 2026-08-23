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
                    },
                    required=["robot", "x", "y"],
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
        ]),
    ]


ROBOT_TOOLS = get_robot_tools()


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
                description="Take an overhead photo and detect all objects (kitchenware: dishes/plates, cups/mugs, long bar, and colored blocks/cylinders) on the tables. Returns list of objects with positions.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="pick",
                description="Command a single robot arm to pick up a specific object (kitchenware dishes, cups, or colored blocks).",
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
                            description="Label, color, or type of the object to pick, e.g. 'Dish1', 'Cup1', 'White Plate', 'Coffee Mug', 'Red Cube', 'Block1'."
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Movement speed ('fast' strongly recommended for high throughput and agility, 'normal' for standard transport). Default is 'fast'."
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
                description="Place the currently held object at the specified absolute world X, Y coordinates (e.g. central dining table, side counters, place settings). Z-height is automatically calculated based on the surface or stacked objects.",
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
                            description="Optional: Movement speed ('fast' strongly recommended for high throughput and agility, 'normal' for standard transport). Default is 'fast'."
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
                description="Place the currently held object relative to an existing object on the table (e.g. place cup right_of dish, stack plate on_top_of plate, or arrange blocks). Coordinates and spacing are automatically calculated based on object affordances.",
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
                            description="The name of the object already placed to use as reference (e.g., 'Dish1', 'Cup1', 'Block1', 'White Plate', 'Red Cube')."
                        ),
                        "relation": types.Schema(
                            type="STRING",
                            enum=["on_top_of", "left_of", "right_of", "front_of", "back_of"],
                            description="Where to place the object relative to the anchor object. 'on_top_of' stacks it. 'left_of', 'right_of', 'front_of', 'back_of' place it adjacently (e.g. cup to the right of a dish)."
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Movement speed ('fast' strongly recommended for high throughput and agility, 'normal' for standard transport). Default is 'fast'."
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
                name="dual_arm_transport",
                description="Command two adjacent robot arms to simultaneously grasp opposite ends of an oversized object (e.g. LongBar1, serving tray), synchronously lift, transport along a coupled Cartesian trajectory maintaining rigid grasp separation, and place it at the target destination.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robots": types.Schema(
                            type="ARRAY",
                            items=types.Schema(type="STRING", enum=["FR3_1", "FR3_2", "FR3_3"]),
                            description="Pair of two adjacent robot arms executing collaborative transport, e.g. ['FR3_1', 'FR3_2'] or ['FR3_2', 'FR3_3']."
                        ),
                        "object_label": types.Schema(
                            type="STRING",
                            description="Label of the oversized object to collaboratively transport, e.g. 'LongBar', 'LongBar1', 'Serving Tray'."
                        ),
                        "object": types.Schema(
                            type="STRING",
                            description="Optional canonical name or alias for the object (e.g. 'LongBar1')."
                        ),
                        "destination": types.Schema(
                            type="ARRAY",
                            items=types.Schema(type="NUMBER"),
                            description="Target destination coordinates [x, y, z] in world frame (e.g. [0.0, 0.0, 0.05])."
                        ),
                        "target_position": types.Schema(
                            type="ARRAY",
                            items=types.Schema(type="NUMBER"),
                            description="Optional: Target destination [x, y, z] in world frame (e.g. [0.0, 0.0, 0.05])."
                        ),
                        "target_x": types.Schema(
                            type="NUMBER",
                            description="Target destination center X coordinate in world frame."
                        ),
                        "target_y": types.Schema(
                            type="NUMBER",
                            description="Target destination center Y coordinate in world frame."
                        ),
                        "target_z": types.Schema(
                            type="NUMBER",
                            description="Optional: Target destination center Z coordinate in world frame. Default is 0.05."
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Movement speed ('fast' strongly recommended for agile trajectory tracking). Default is 'fast'."
                        ),
                        "sync_mode": types.Schema(
                            type="STRING",
                            enum=["rigid_body", "leader_follower"],
                            description="Optional: Kinematic coordination mode ('rigid_body' for constant grasp separation). Default is 'rigid_body'."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover height above grasp points before descending (meters). Default is 0.12."
                        ),
                    },
                    required=["robots", "object_label"],
                ),
            ),
            types.FunctionDeclaration(
                name="clear_table",
                description="Command a single robot arm to clear kitchenware (dishes, cups) from the central table to dedicated clearing zones (dish rack, cup tray, or side counter).",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robot": types.Schema(
                            type="STRING",
                            enum=["FR3_1", "FR3_2", "FR3_3"],
                            description="Which robot arm to dispatch for clearing."
                        ),
                        "object_label": types.Schema(
                            type="STRING",
                            description="Optional: Specific kitchenware object to clear (e.g. 'Dish1', 'Cup1'). If omitted, clears the nearest item."
                        ),
                        "zone": types.Schema(
                            type="STRING",
                            enum=["counter", "dish_rack", "cup_tray"],
                            description="Clearing destination zone. Default is 'counter'."
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Movement speed ('fast' recommended). Default is 'fast'."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover approach height (meters). Default is 0.10."
                        ),
                    },
                    required=["robot"],
                ),
            ),
            types.FunctionDeclaration(
                name="organize_table",
                description="Command a single robot arm to arrange kitchenware (dishes, cups) into designated place settings or dining layout configurations on the central dining table.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "robot": types.Schema(
                            type="STRING",
                            enum=["FR3_1", "FR3_2", "FR3_3"],
                            description="Which robot arm to dispatch for organizing."
                        ),
                        "object_label": types.Schema(
                            type="STRING",
                            description="Optional: Specific kitchenware object to organize (e.g. 'Dish1', 'Cup1')."
                        ),
                        "layout": types.Schema(
                            type="STRING",
                            enum=["dining", "tea_service", "buffet"],
                            description="Target organization layout. Default is 'dining'."
                        ),
                        "speed": types.Schema(
                            type="STRING",
                            enum=["fast", "normal", "slow"],
                            description="Optional: Movement speed ('fast' recommended). Default is 'fast'."
                        ),
                        "approach_height": types.Schema(
                            type="NUMBER",
                            description="Optional: Hover approach height (meters). Default is 0.10."
                        ),
                    },
                    required=["robot"],
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

# Dictionary definitions of all tool schemas for inspection without google.genai dependency
GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "detect_objects",
        "description": "Take an overhead photo and detect all objects (kitchenware: dishes/plates, cups/mugs, long bar, and colored blocks/cylinders) on the tables. Returns list of objects with positions.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "pick",
        "description": "Command a single robot arm to pick up a specific object (kitchenware dishes, cups, or colored blocks).",
        "parameters": {
            "type": "object",
            "properties": {
                "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]},
                "object_label": {"type": "string"},
                "speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
                "approach_height": {"type": "number"}
            },
            "required": ["robot", "object_label"]
        }
    },
    {
        "name": "place",
        "description": "Place the currently held object at the specified absolute world X, Y coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
                "approach_height": {"type": "number"}
            },
            "required": ["robot", "x", "y"]
        }
    },
    {
        "name": "place_relative",
        "description": "Place the currently held object relative to an existing object on the table.",
        "parameters": {
            "type": "object",
            "properties": {
                "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]},
                "anchor_block": {"type": "string"},
                "relation": {"type": "string", "enum": ["on_top_of", "left_of", "right_of", "front_of", "back_of"]},
                "speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
                "approach_height": {"type": "number"}
            },
            "required": ["robot", "anchor_block", "relation"]
        }
    },
    {
        "name": "dual_arm_transport",
        "description": "Command two adjacent robot arms to simultaneously grasp opposite ends of an oversized object (e.g. LongBar1, serving tray), synchronously lift, transport along a coupled Cartesian trajectory maintaining rigid grasp separation, and place it at the target destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "robots": {"type": "array", "items": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]}},
                "object_label": {"type": "string"},
                "object": {"type": "string"},
                "destination": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "target_position": {"type": "array", "items": {"type": "number"}},
                "target_x": {"type": "number"},
                "target_y": {"type": "number"},
                "target_z": {"type": "number"},
                "speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
                "sync_mode": {"type": "string", "enum": ["rigid_body", "leader_follower"]},
                "approach_height": {"type": "number"}
            },
            "required": ["robots", "object_label"]
        }
    },
    {
        "name": "clear_table",
        "description": "Command a single robot arm to clear kitchenware (dishes, cups) from the central table to dedicated clearing zones.",
        "parameters": {
            "type": "object",
            "properties": {
                "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]},
                "object_label": {"type": "string"},
                "zone": {"type": "string", "enum": ["counter", "dish_rack", "cup_tray"]},
                "speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
                "approach_height": {"type": "number"}
            },
            "required": ["robot"]
        }
    },
    {
        "name": "organize_table",
        "description": "Command a single robot arm to arrange kitchenware (dishes, cups) into designated place settings or dining layout configurations.",
        "parameters": {
            "type": "object",
            "properties": {
                "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]},
                "object_label": {"type": "string"},
                "layout": {"type": "string", "enum": ["dining", "tea_service", "buffet"]},
                "speed": {"type": "string", "enum": ["fast", "normal", "slow"]},
                "approach_height": {"type": "number"}
            },
            "required": ["robot"]
        }
    },
    {
        "name": "verify_tower",
        "description": "Take a new overhead photo and verify the current workspace state.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "go_home",
        "description": "Send a robot arm back to its home/rest position.",
        "parameters": {
            "type": "object",
            "properties": {
                "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]}
            },
            "required": ["robot"]
        }
    },
    {
        "name": "get_workspace_status",
        "description": "Get the current state of all robots and objects.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "replan",
        "description": "Trigger a full re-evaluation of the workspace via a multi-agent brainstorm.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]



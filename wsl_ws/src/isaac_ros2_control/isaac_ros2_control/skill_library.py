"""
Agentic Task and Motion Planning (ATAMP) - Skill Library (Late 2026 SOTA)
Provides a dynamically queryable and parameterizable repository of robotic skills
for long-horizon industrial assembly tasks.
"""

try:
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    types = None
    GENAI_AVAILABLE = False


class SkillLibrary:
    def __init__(self):
        self.skills = {}
        self._register_base_skills()

    def _register_base_skills(self):
        if not GENAI_AVAILABLE: return
        
        # 1. Single Arm Spatial Manipulation
        self.skills['pick_and_place'] = types.FunctionDeclaration(
            name="pick_and_place",
            description="Sequence a single arm to pick an object and place it at a target. Modifiable parameters for approach vector and clearance.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "robot": types.Schema(type="STRING", description="FR3_1 or FR3_2"),
                    "object_label": types.Schema(type="STRING"),
                    "target_x": types.Schema(type="NUMBER"),
                    "target_y": types.Schema(type="NUMBER"),
                    "approach_z_clearance": types.Schema(type="NUMBER", description="Z-height clearance for obstacle avoidance (e.g. 0.2m)"),
                },
                required=["robot", "object_label", "target_x", "target_y"]
            )
        )

        # 2. Precision Insertion (For Gears/Pegs)
        self.skills['precision_insert'] = types.FunctionDeclaration(
            name="precision_insert",
            description="High-precision insertion of a peg/gear into a hole/chassis. Requires force-compliance.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "robot": types.Schema(type="STRING"),
                    "object_label": types.Schema(type="STRING", description="E.g., 'Gear1'"),
                    "receptacle_label": types.Schema(type="STRING", description="E.g., 'Chassis_Slot_A'"),
                    "stiffness": types.Schema(type="STRING", enum=["rigid", "compliant"], description="Use 'compliant' to avoid jamming."),
                },
                required=["robot", "object_label", "receptacle_label", "stiffness"]
            )
        )

        # 3. Collaborative Dual-Arm Transport (Heavy objects)
        self.skills['dual_arm_transport'] = types.FunctionDeclaration(
            name="dual_arm_transport",
            description="Command BOTH arms to synchronously grasp and transport a heavy/oversized object.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "object_label": types.Schema(type="STRING", description="E.g., 'HeavyChassis'"),
                    "offset_1": types.Schema(type="NUMBER", description="FR3_1 geometric grasp offset (m)"),
                    "offset_2": types.Schema(type="NUMBER", description="FR3_2 geometric grasp offset (m)"),
                    "target_x": types.Schema(type="NUMBER"),
                    "target_y": types.Schema(type="NUMBER"),
                },
                required=["object_label", "offset_1", "offset_2", "target_x", "target_y"]
            )
        )

        # 4. Bimanual Handover (Spatial efficiency)
        self.skills['bimanual_handover'] = types.FunctionDeclaration(
            name="bimanual_handover",
            description="Hand over an object from one robot arm to the other in mid-air to bypass workspace limits.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "from_robot": types.Schema(type="STRING"),
                    "to_robot": types.Schema(type="STRING"),
                    "object_label": types.Schema(type="STRING"),
                    "handover_x": types.Schema(type="NUMBER", description="Mid-point X coordinate"),
                    "handover_y": types.Schema(type="NUMBER", description="Mid-point Y coordinate"),
                },
                required=["from_robot", "to_robot", "object_label", "handover_x", "handover_y"]
            )
        )

        # 5. Non-prehensile push/clear (Obstacle clearance)
        self.skills['compliant_push'] = types.FunctionDeclaration(
            name="compliant_push",
            description="Push an obstructing object out of the way without fully grasping it.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "robot": types.Schema(type="STRING"),
                    "obstacle_label": types.Schema(type="STRING"),
                    "push_direction_x": types.Schema(type="NUMBER", description="Unit vector X"),
                    "push_direction_y": types.Schema(type="NUMBER", description="Unit vector Y"),
                },
                required=["robot", "obstacle_label", "push_direction_x", "push_direction_y"]
            )
        )
        
        # Meta-skills
        self.skills['get_workspace_status'] = types.FunctionDeclaration(
            name="get_workspace_status",
            description="Get the current state of all robots and objects.",
            parameters=types.Schema(type="OBJECT", properties={})
        )

    def get_all_skills(self):
        return [types.Tool(function_declarations=list(self.skills.values()))]

skill_library = SkillLibrary()

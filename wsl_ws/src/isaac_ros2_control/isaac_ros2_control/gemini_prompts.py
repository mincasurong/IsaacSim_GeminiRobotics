"""Structured prompt templates for Gemini Robotics-ER 2 function calling.
"""
try:
    from isaac_ros2_control.workspace_config import WORKSPACE
except ImportError:
    try:
        from .workspace_config import WORKSPACE
    except ImportError:
        from workspace_config import WORKSPACE

# Function Calling System Prompt
_T1 = WORKSPACE['robots']['FR3_1']['table_center']
_T2 = WORKSPACE['robots']['FR3_2']['table_center']
_T3 = WORKSPACE['robots']['FR3_3']['table_center']
_CB = WORKSPACE['central_table']['bounds']

SYSTEM_PROMPT = f"""\
You are an advanced, autonomous Vision-Language-Action (VLA) robotic orchestrator powered by Gemini Robotics-ER-2, controlling 3 Franka FR3 robot arms.
{{user_goal}}

Workspace Layout & Physical Kinematic Constraints:
- FR3_1 (Bottom arm): Operates exclusively on Source Table 1 ([X={_T1[0]}, Y={_T1[1]}]) and the Central Target Table.
  • Reachable blocks: Block1 (Red Cube), Block2 (Green Cylinder), Block3 (Blue Cube).
- FR3_2 (Top-Right arm): Operates exclusively on Source Table 2 ([X={_T2[0]}, Y={_T2[1]}]) and the Central Target Table.
  • Reachable blocks: Block4 (Yellow Cylinder), Block5 (Magenta Cube), Block6 (Cyan Cylinder).
- FR3_3 (Top-Left arm): Operates exclusively on Source Table 3 ([X={_T3[0]}, Y={_T3[1]}]) and the Central Target Table.
  • Reachable blocks: Block7 (Orange Cube), Block8 (Purple Cylinder), Block9 (Lime Cube).
- Central Target Table ([0.0, 0.0]): Shared staging/stacking table within bounds X=[{_CB[0][0]}, {_CB[0][1]}], Y=[{_CB[1][0]}, {_CB[1][1]}]. All arms place here.

Pre-execution Rule-Based Safety Verification:
- All function calls are inspected and validated by the Rule-Based Task Verifier before physical execution.
- Cross-table pick violations (e.g. asking FR3_1 to pick Block5 on Table 2) will be blocked.
- Follow the provided Grounded Rule-Based Blueprint to select valid, unstacked blocks for each robot.

Autonomous Execution Rules:
1. Grounded Task Execution: Follow the Rule-Based Blueprint stacking order (round-robin: FR3_1 -> FR3_2 -> FR3_3) to systematically build the tower.
2. Placement:
   - For tower stacking on the center table, use `place(robot=..., x=0.0, y=0.0)` or `place_relative(anchor_block=..., relation="on_top_of")`.
   - Never specify placement coordinates outside the Central Target Table (|x| <= 0.15m, |y| <= 0.15m).
3. Maximum Multi-Robot Concurrency:
   - You can dispatch commands to multiple robots simultaneously (e.g., dispatching FR3_1 and FR3_2 to pick at the same time).
   - DO NOT issue multiple conflicting commands to the SAME robot in a single turn. Always wait for a pick to complete before placing.
   - Use `speed='fast'` for snappy, responsive trajectories.
4. Available Tools: detect_objects, pick, place, place_relative, verify_tower, go_home, get_workspace_status, replan.
"""

# Recovery Prompt
PICK_FAILURE_CONTEXT = """\
⚠️ Pick failed for {block} by {robot}. Failure count: {count}/2.
Updated workspace status: {status}
Re-detect objects and try an alternative block or approach strategy.
"""

# Detection & Verification Prompts

DETECT_BLOCKS_PROMPT = """\
You are observing a multi-robot manipulation workspace from an overhead camera.
The workspace contains source tables and a central target table with colored objects (such as cubes and cylinders).

Identify ALL visible target objects on the tables.
Return their normalized coordinates and descriptive labels in exact JSON format:
[{"point": [y, x], "label": "<color> <shape>"}, ...]

Points must be [y, x] normalized from 0 to 1000. Do NOT include markdown code fences or conversational text.
"""

VERIFY_PLACEMENT_PROMPT = """\
Examine this overhead camera view of the central target table after objects were placed.

Determine:
1. Is the construction physically stable?
2. Are any blocks tipping, misaligned, or fallen?
3. What shapes or structures have been built on the central table?

Respond with valid JSON only:
{"success": true, "issues": "<description or empty>", "assessment": "<briefly describe what is built>"}
"""

DESCRIBE_SCENE_PROMPT = """\
Describe this multi-robot manipulation workspace in detail:
- Positions and status of FR3_1, FR3_2, FR3_3
- Objects present across the source tables and the Central Target Table
- Current layer height and alignment of the construction
- Spatial layout and any observed workspace collisions
"""

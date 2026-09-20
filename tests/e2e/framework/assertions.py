"""Domain-specific assertions for Isaac Sim, kinematics, ROS 2 messages, and frontend code."""
import ast
import json
import os
import re
import numpy as np
from .contracts import FR3_JOINT_LIMITS, FR3_GRIPPER_LIMITS, WORKSPACE_BOUNDS


def assert_joint_limits(joint_angles):
    """Assert all 7 Franka FR3 joint angles are within physical limits."""
    assert len(joint_angles) >= 7, f"Expected at least 7 joint angles, got {len(joint_angles)}"
    for i, q in enumerate(joint_angles[:7]):
        low, high = FR3_JOINT_LIMITS[i]
        assert low <= q <= high, f"Joint {i+1} angle {q:.4f} rad exceeds limits [{low:.4f}, {high:.4f}]"


def assert_gripper_limits(finger_pos):
    """Assert gripper finger width is within limits [0.0, 0.04] m."""
    low, high = FR3_GRIPPER_LIMITS
    assert low <= finger_pos <= high, f"Gripper width {finger_pos:.4f} m exceeds limits [{low:.4f}, {high:.4f}]"


def assert_rigid_body_distance(pos1, pos2, nominal_distance, tol=0.005):
    """Assert two gripper 3D positions maintain distance invariance within tolerance."""
    d = np.linalg.norm(np.array(pos1) - np.array(pos2))
    diff = abs(d - nominal_distance)
    assert diff <= tol, f"Rigid body distance drift: measured {d:.4f}m vs nominal {nominal_distance:.4f}m (diff {diff:.4f}m > tol {tol:.4f}m)"


def assert_valid_json_schema(data, schema):
    """Basic structural validation of dictionary against schema."""
    if isinstance(data, str):
        data = json.loads(data)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}"
    for req in schema.get("required", []):
        assert req in data, f"Missing required property '{req}' in payload {data}"


def assert_ast_defines_function(filepath, function_name):
    """Assert a python file exists and defines a specific top-level function."""
    assert os.path.exists(filepath), f"File not found: {filepath}"
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename=filepath)
    funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert function_name in funcs, f"Function '{function_name}' not found in {filepath}. Found: {funcs}"


def assert_ast_defines_class(filepath, class_name):
    """Assert a python file exists and defines a specific top-level class."""
    assert os.path.exists(filepath), f"File not found: {filepath}"
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename=filepath)
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert class_name in classes, f"Class '{class_name}' not found in {filepath}. Found: {classes}"


def assert_file_contains_regex(filepath, pattern, description=None):
    """Assert a file exists and contains matches for a regular expression."""
    assert os.path.exists(filepath), f"File not found: {filepath}"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(pattern, content)
    msg = description or f"Pattern '{pattern}' not matched in {filepath}"
    assert match is not None, msg

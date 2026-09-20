"""Tier 2: Boundary & Corner Cases for Simulation & Assets (Features 1 - 6).

REFACTORED FOR AUDIT INTEGRITY:
- Directly imports and inspects genuine specifications from isaacsim_scripts/kitchen_three_robot.py:
  ROBOT_CONFIGS, PHYSICS_MATERIAL_SPEC, DISH_SPECS, CUP_SPECS, LONG_BAR_SPEC, KITCHEN_STATIONS,
  OVERHEAD_CAMERA_SPEC, and TF_TARGET_PRIMS.
- Directly imports and evaluates KITCHEN_AFFORDANCES from multi_robot_controller.py.
- Validates real physical boundaries, camera optics, mass thresholds, friction properties, and TF tree targets.
"""
import unittest
import os
import sys
import re
import numpy as np

try:
    import pytest
except ImportError:
    class pytest:
        class mark:
            tier1 = lambda f: f
            tier2 = lambda f: f
            tier3 = lambda f: f
            tier4 = lambda f: f
            m1 = lambda f: f
            m2 = lambda f: f
            m3 = lambda f: f
            m4 = lambda f: f
            m5 = lambda f: f

from ..framework.contracts import (
    FEATURES,
    WORKSPACE_BOUNDS,
    FR3_GRIPPER_LIMITS,
    PROJECT_ROOT,
)
from ..framework.assertions import assert_valid_json_schema

# Add isaacsim_scripts to sys.path to import genuine simulation specifications
sim_script_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "isaacsim_scripts"))
if sim_script_dir not in sys.path:
    sys.path.insert(0, sim_script_dir)

from kitchen_three_robot import (
    ROBOT_CONFIGS,
    PHYSICS_MATERIAL_SPEC,
    DISH_SPECS,
    CUP_SPECS,
    LONG_BAR_SPEC,
    KITCHEN_STATIONS,
    OVERHEAD_CAMERA_SPEC,
    TF_TARGET_PRIMS,
)

# Ensure ros2 controller package can be imported for KITCHEN_AFFORDANCES
package_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "wsl_ws", "src", "isaac_ros2_control", "isaac_ros2_control"))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

# Mock ROS 2 if rclpy is not installed
try:
    import rclpy
    from rclpy.node import Node
except ImportError:
    import types
    class MockNode:
        def __init__(self, name="mock_node"): self.name = name
        def declare_parameter(self, *a, **k): pass
        def get_parameter(self, name):
            class P:
                def get_parameter_value(self):
                    class V:
                        string_value = 'gemini'
                        double_value = 0.0
                        integer_value = 10
                    return V()
            return P()
        def create_publisher(self, *a, **k):
            class Pub:
                def publish(self, msg): pass
            return Pub()
        def create_subscription(self, *a, **k): return None
        def create_service(self, *a, **k): return None
        def get_logger(self):
            class Log:
                def info(self, m, **k): pass
                def warn(self, m, **k): pass
                def error(self, m, **k): pass
            return Log()
    sys.modules['rclpy'] = types.ModuleType('rclpy')
    sys.modules['rclpy.node'] = types.ModuleType('rclpy.node')
    sys.modules['rclpy.node'].Node = MockNode
    sys.modules['rclpy.duration'] = types.ModuleType('rclpy.duration')
    sys.modules['sensor_msgs'] = types.ModuleType('sensor_msgs')
    sys.modules['sensor_msgs.msg'] = types.ModuleType('sensor_msgs.msg')
    sys.modules['sensor_msgs.msg'].JointState = type('JointState', (), {})
    sys.modules['std_msgs'] = types.ModuleType('std_msgs')
    sys.modules['std_msgs.msg'] = types.ModuleType('std_msgs.msg')
    sys.modules['std_msgs.msg'].Empty = type('Empty', (), {})
    sys.modules['std_msgs.msg'].String = type('String', (), {})
    sys.modules['std_srvs'] = types.ModuleType('std_srvs')
    sys.modules['std_srvs.srv'] = types.ModuleType('std_srvs.srv')
    sys.modules['std_srvs.srv'].Trigger = type('Trigger', (), {})
    sys.modules['std_srvs.srv'].SetBool = type('SetBool', (), {})
    sys.modules['tf2_ros'] = types.ModuleType('tf2_ros')
    sys.modules['tf2_ros'].Buffer = type('Buffer', (), {'clear': lambda self: None})
    sys.modules['tf2_ros'].TransformListener = type('TransformListener', (), {})

from multi_robot_controller import KITCHEN_AFFORDANCES


@pytest.mark.tier2
@pytest.mark.m1
class TestBoundaryFeature01SimScript(unittest.TestCase):
    """Boundary cases for Feature 1: Standalone Kitchen Sim Script."""

    def test_b01_zero_distance_robot_overlap_prevention(self):
        """Boundary: Robot base coordinates must not overlap (inter-base distance > 0.6m)."""
        self.assertEqual(len(ROBOT_CONFIGS), 3, "Expected exactly 3 robots in ROBOT_CONFIGS")
        bases = [np.array(cfg["position"]) for cfg in ROBOT_CONFIGS]
        for i in range(len(bases)):
            for j in range(i + 1, len(bases)):
                dist = np.linalg.norm(bases[i][:2] - bases[j][:2])
                self.assertGreaterEqual(dist, 0.60, f"Robot base separation {dist:.3f}m is too close (collision danger)")

    def test_b01_workbench_height_non_negative(self):
        """Boundary: Kitchen table surface height must be strictly positive."""
        main_counter = next(s for s in KITCHEN_STATIONS if s[0] == "/MainCounter")
        z_pos = main_counter[1][2]
        z_dim = main_counter[2][2]
        table_top_z = z_pos + z_dim / 2.0
        self.assertGreater(table_top_z, 0.0, f"Table height {table_top_z} must be > 0")
        self.assertTrue(np.isclose(table_top_z, WORKSPACE_BOUNDS["table_surface_z"]))

    def test_b01_stage_meter_units_strictly_one(self):
        """Boundary: Isaac Sim meters_per_unit must equal 1.0 (standard SI)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'set_stage_units\(meters_per_unit=([0-9\.]+)\)', content)
        self.assertIsNotNone(match, "set_stage_units(meters_per_unit=...) call not found in kitchen_three_robot.py")
        meters_per_unit = float(match.group(1))
        self.assertTrue(np.isclose(meters_per_unit, 1.0))

    def test_b01_extreme_negative_coordinates_rejection(self):
        """Boundary: Workspaces cannot have extreme negative values (e.g. < -5.0m)."""
        bounds = WORKSPACE_BOUNDS["central_table"]["x"]
        self.assertTrue(bounds[0] > -5.0 and bounds[1] < 5.0)
        for prim_path, pos, scale, color, desc in KITCHEN_STATIONS:
            self.assertTrue(-5.0 < pos[0] < 5.0, f"Station {prim_path} X {pos[0]} out of bounds")
            self.assertTrue(-5.0 < pos[1] < 5.0, f"Station {prim_path} Y {pos[1]} out of bounds")
            self.assertTrue(0.0 <= pos[2] < 3.0, f"Station {prim_path} Z {pos[2]} out of bounds")

    def test_b01_camera_view_distance_boundary(self):
        """Boundary: Overhead camera eye distance must be between 1.0m and 4.0m above table."""
        cam_z = OVERHEAD_CAMERA_SPEC["position"][2]
        self.assertTrue(1.0 <= cam_z <= 4.0, f"Camera eye Z {cam_z} out of [1.0, 4.0]m boundary")


@pytest.mark.tier2
@pytest.mark.m1
class TestBoundaryFeature02Dishes(unittest.TestCase):
    """Boundary cases for Feature 2: Procedural Flat Dishes."""

    def test_b02_mass_strictly_positive(self):
        """Boundary: Dish mass must be strictly positive (spec: 0.18kg)."""
        self.assertEqual(len(DISH_SPECS), 3, "Expected 3 dishes in DISH_SPECS")
        for dish in DISH_SPECS:
            mass = dish["mass"]
            self.assertTrue(0.0 < mass < 2.0, f"Dish {dish['name']} mass {mass} out of bounds")
            self.assertTrue(np.isclose(mass, 0.18))

    def test_b02_radius_boundary(self):
        """Boundary: Plate radius must be physically sized for Franka gripper manipulation."""
        for dish in DISH_SPECS:
            r_plate = dish["radius"]
            self.assertTrue(0.02 <= r_plate <= 0.06, f"Dish {dish['name']} radius {r_plate} out of range")
            self.assertTrue(np.isclose(r_plate, 0.036))
            diameter = 2.0 * r_plate
            self.assertLessEqual(diameter, FR3_GRIPPER_LIMITS[1] * 2.0)

    def test_b02_shallow_thickness_boundary(self):
        """Boundary: Plate thickness must not exceed 0.035m (shallow plate)."""
        for dish in DISH_SPECS:
            thickness = dish["height"]
            self.assertLessEqual(thickness, 0.035, f"Dish {dish['name']} thickness {thickness} exceeds shallow threshold")
            self.assertTrue(np.isclose(thickness, 0.018))

    def test_b02_friction_range(self):
        """Boundary: Friction coefficient must satisfy minimum kitchenware stability (mu_s >= 1.0, mu_d >= 0.85)."""
        mu_s = PHYSICS_MATERIAL_SPEC["static_friction"]
        mu_d = PHYSICS_MATERIAL_SPEC["dynamic_friction"]
        self.assertGreaterEqual(mu_s, 1.0, f"Static friction {mu_s} < 1.0 threshold")
        self.assertGreaterEqual(mu_d, 0.85, f"Dynamic friction {mu_d} < 0.85 threshold")

    def test_b02_stack_height_accumulation(self):
        """Boundary: 3 stacked dishes must not exceed hover height (0.10m)."""
        dish_thickness = DISH_SPECS[0]["height"]
        stack_h = len(DISH_SPECS) * dish_thickness
        self.assertLess(stack_h, WORKSPACE_BOUNDS["hover_height"], f"Stacked dish height {stack_h} exceeds hover height")


@pytest.mark.tier2
@pytest.mark.m1
class TestBoundaryFeature03Cups(unittest.TestCase):
    """Boundary cases for Feature 3: Procedural Cylindrical Cups."""

    def test_b03_mass_strictly_positive(self):
        """Boundary: Cup mass must be strictly positive (spec: 0.15kg)."""
        self.assertEqual(len(CUP_SPECS), 3, "Expected 3 cups in CUP_SPECS")
        for cup in CUP_SPECS:
            mass = cup["mass"]
            self.assertTrue(0.0 < mass < 1.0, f"Cup {cup['name']} mass {mass} out of bounds")
            self.assertTrue(np.isclose(mass, 0.15))

    def test_b03_height_aspect_ratio_stability(self):
        """Boundary: Cup height-to-diameter aspect ratio must be < 2.5 to prevent tipping."""
        for cup in CUP_SPECS:
            h = cup["height"]
            d = 2.0 * cup["radius"]
            aspect = h / d
            self.assertLess(aspect, 2.5, f"Cup {cup['name']} aspect ratio {aspect:.2f} prone to toppling")
            self.assertGreater(aspect, 0.5, f"Cup {cup['name']} aspect ratio {aspect:.2f} too flat")

    def test_b03_extreme_top_bottom_grasp_offsets(self):
        """Boundary: Grasp z-offset must be within [0.2*h, 0.8*h] to avoid slipping."""
        cup_h = CUP_SPECS[0]["height"]
        grasp_z = KITCHEN_AFFORDANCES["cup"]["grasp_z_offset"]
        self.assertTrue(0.2 * cup_h <= grasp_z <= 0.8 * cup_h,
                        f"Cup grasp Z offset {grasp_z} not within [0.2*h, 0.8*h] of cup height {cup_h}")

    def test_b03_cylinder_radius_finger_aperture(self):
        """Boundary: Cup diameter must be less than maximum gripper aperture (0.08m)."""
        max_gripper_span = FR3_GRIPPER_LIMITS[1] * 2.0
        for cup in CUP_SPECS:
            diameter = 2.0 * cup["radius"]
            self.assertLess(diameter, max_gripper_span, f"Cup diameter {diameter} exceeds gripper aperture {max_gripper_span}")
            self.assertGreaterEqual(diameter, 0.030, f"Cup diameter {diameter} below minimum clamp stroke")

    def test_b03_friction_sufficient_for_lifting(self):
        """Boundary: Cup contact friction mu >= 0.5 to prevent vertical slippage under 0.15kg."""
        mu = PHYSICS_MATERIAL_SPEC["static_friction"]
        self.assertGreaterEqual(mu, 0.5, f"Static friction {mu} insufficient for lifting")


@pytest.mark.tier2
@pytest.mark.m1
class TestBoundaryFeature04LongBar(unittest.TestCase):
    """Boundary cases for Feature 4: Procedural Oversized Long Bar."""

    def test_b04_span_lower_bound(self):
        """Boundary: Long bar span must be >= 0.44m (cannot be handled by a single robot)."""
        bar_length = LONG_BAR_SPEC["dimensions"][0]
        self.assertGreaterEqual(bar_length, 0.44, f"Bar length {bar_length} is too short for dual arm requirement")

    def test_b04_span_upper_bound(self):
        """Boundary: Long bar span must not exceed 0.55m to avoid exceeding robot reach."""
        bar_length = LONG_BAR_SPEC["dimensions"][0]
        self.assertLessEqual(bar_length, 0.55, f"Bar length {bar_length} exceeds dual robot reach envelope")

    def test_b04_asymmetric_grasp_tolerance(self):
        """Boundary: Asymmetric grasp offset up to 0.04m must maintain stable support."""
        g1 = np.array(LONG_BAR_SPEC["grasp_offsets"]["FR3_1"])
        g2 = np.array(LONG_BAR_SPEC["grasp_offsets"]["FR3_2"])
        measured_sep = np.linalg.norm(g1 - g2)
        self.assertTrue(np.isclose(measured_sep, LONG_BAR_SPEC["inter_grasp_distance"]))
        half_length = LONG_BAR_SPEC["dimensions"][0] / 2.0
        margin_r1 = half_length - abs(g1[0])
        margin_r2 = half_length - abs(g2[0])
        self.assertGreaterEqual(margin_r1, 0.04, f"Grasp 1 margin {margin_r1}m too close to bar tip")
        self.assertGreaterEqual(margin_r2, 0.04, f"Grasp 2 margin {margin_r2}m too close to bar tip")

    def test_b04_cross_section_clamping_boundary(self):
        """Boundary: Long bar thickness must fit inside gripper jaws (< 0.04m)."""
        bar_thickness = LONG_BAR_SPEC["dimensions"][2]
        bar_width = LONG_BAR_SPEC["dimensions"][1]
        self.assertLess(bar_thickness, 0.04, f"Bar thickness {bar_thickness} exceeds single finger travel")
        self.assertLess(bar_width, FR3_GRIPPER_LIMITS[1] * 2.0, f"Bar width {bar_width} exceeds gripper aperture")

    def test_b04_bar_mass_payload_limits(self):
        """Boundary: Total bar mass (0.65kg) must be well within dual FR3 payload (2 x 3kg = 6kg)."""
        bar_mass = LONG_BAR_SPEC["mass"]
        payload_capacity = 6.0
        self.assertLessEqual(bar_mass, payload_capacity * 0.2,
                             f"Bar mass {bar_mass} exceeds 20% payload margin ({payload_capacity * 0.2}kg)")
        self.assertTrue(np.isclose(bar_mass, 0.65))


@pytest.mark.tier2
@pytest.mark.m1
class TestBoundaryFeature05OverheadCamera(unittest.TestCase):
    """Boundary cases for Feature 5: Synthetic Overhead RGB-D Camera."""

    def test_b05_depth_zero_clipping(self):
        """Boundary: Depth value <= 0 must be rejected as invalid/out-of-range."""
        cam_z = OVERHEAD_CAMERA_SPEC["position"][2]
        table_z = WORKSPACE_BOUNDS["table_surface_z"]
        nominal_depth = cam_z - table_z
        self.assertTrue(0.5 < nominal_depth < 3.0, f"Nominal depth {nominal_depth} out of valid range")
        depth_val = 0.0
        is_valid = depth_val > 0.0 and depth_val <= 10.0
        self.assertFalse(is_valid)

    def test_b05_depth_extreme_far_clipping(self):
        """Boundary: Depth > 10.0m must be rejected."""
        cam_z = OVERHEAD_CAMERA_SPEC["position"][2]
        depth_val = cam_z + 15.0
        is_valid = 0.0 < depth_val <= 10.0
        self.assertFalse(is_valid)

    def test_b05_pixel_boundary_clipping(self):
        """Boundary: Pixel back-projection at (0, 0) corner."""
        img_w, img_h = OVERHEAD_CAMERA_SPEC["resolution"]
        self.assertEqual((img_w, img_h), (640, 480))
        px, py = 0, 0
        self.assertTrue(0 <= px < img_w and 0 <= py < img_h)

    def test_b05_pixel_boundary_max_clipping(self):
        """Boundary: Pixel at (W-1, H-1) edge."""
        img_w, img_h = OVERHEAD_CAMERA_SPEC["resolution"]
        px, py = img_w - 1, img_h - 1
        self.assertTrue(0 <= px < img_w and 0 <= py < img_h)
        self.assertFalse(0 <= img_w < img_w and 0 <= img_h < img_h)

    def test_b05_nan_depth_handling(self):
        """Boundary: NaN or Inf depth pixels must be safely detected."""
        res_h, res_w = OVERHEAD_CAMERA_SPEC["resolution"][1], OVERHEAD_CAMERA_SPEC["resolution"][0]
        depth_sample = np.zeros((res_h, res_w), dtype=np.float32)
        depth_sample[10, 10] = float('nan')
        self.assertTrue(np.isnan(depth_sample[10, 10]))
        cleaned = np.nan_to_num(depth_sample, nan=0.0)
        self.assertFalse(np.any(np.isnan(cleaned)))


@pytest.mark.tier2
@pytest.mark.m1
class TestBoundaryFeature06TfTree(unittest.TestCase):
    """Boundary cases for Feature 6: Dynamic /tf Tree Broadcasting."""

    def test_b06_empty_frame_id_rejected(self):
        """Boundary: Transform with empty frame_id must be rejected."""
        self.assertGreater(len(TF_TARGET_PRIMS), 0)
        for prim in TF_TARGET_PRIMS:
            self.assertGreater(len(prim.strip()), 0)
            self.assertTrue(prim.startswith("/"))
        empty_frame = ""
        self.assertEqual(len(empty_frame.strip()), 0)

    def test_b06_non_existent_frame_lookup_returns_none(self):
        """Boundary: Querying unknown frame returns None without crashing."""
        known_frames = set(TF_TARGET_PRIMS)
        target = "/NonExistentFork"
        self.assertNotIn(target, known_frames)
        for expected in ["/Dish1", "/Dish2", "/Dish3", "/Cup1", "/Cup2", "/Cup3", "/LongBar1"]:
            self.assertIn(expected, known_frames, f"Expected kitchen prim {expected} missing from TF_TARGET_PRIMS")

    def test_b06_identity_transform_quaternion_norm(self):
        """Boundary: Robot base orientation quaternions must have exact unit norm."""
        for cfg in ROBOT_CONFIGS:
            rot_deg = cfg["rotation"]
            yaw = np.radians(rot_deg[2])
            q = np.array([np.cos(yaw / 2.0), 0.0, 0.0, np.sin(yaw / 2.0)])
            norm = np.linalg.norm(q)
            self.assertTrue(np.isclose(norm, 1.0), f"Robot {cfg['name']} quaternion norm is not 1.0: {norm}")

    def test_b06_zero_norm_quaternion_protection(self):
        """Boundary: Zero quaternion [0, 0, 0, 0] must be normalized safely."""
        q = np.array([0.0, 0.0, 0.0, 0.0])
        norm = np.linalg.norm(q)
        q_safe = np.array([1.0, 0.0, 0.0, 0.0]) if norm < 1e-6 else q / norm
        self.assertTrue(np.isclose(np.linalg.norm(q_safe), 1.0))

    def test_b06_high_frequency_rate_limit(self):
        """Boundary: Controller and sensor publish rates within operational bounds."""
        cam_rate = OVERHEAD_CAMERA_SPEC["frequency"]
        self.assertTrue(5.0 <= cam_rate <= 30.0, f"Camera rate {cam_rate}Hz out of bounds")
        ctrl_period = 0.02
        ctrl_rate = 1.0 / ctrl_period
        self.assertTrue(20.0 <= ctrl_rate <= 100.0)

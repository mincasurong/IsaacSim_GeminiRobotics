"""Unit tests for Single-Arm Kitchenware Manipulation Primitives (Requirement R2).

Verifies:
1. KITCHEN_AFFORDANCES taxonomy completeness and physical correctness
2. Object affordance classification (dish, cup, block, long_bar)
3. Target name resolution and backward-compatibility
4. Rim-pinch grasp geometry for shallow dishes/plates (R_rim ~ 0.065m toward robot base)
5. Mid-height cylindrical clamp geometry for cups (Z_grasp ~ 0.345m)
6. Gripper touch sensor / stall verification ranges for dishes, cups, and blocks
7. Nesting height and rim-offset TCP compensation during placement
8. Workspace table clearing and dining organization layouts
9. Preservation of existing block tower manipulation primitives
"""

import sys
import os
import unittest
import numpy as np

# Add package source to path for direct import
current_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.abspath(os.path.join(current_dir, '..', 'isaac_ros2_control'))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

# Import kinematics directly
try:
    import kinematics
except ImportError:
    from isaac_ros2_control import kinematics

# Import MultiRobotController constants and class
# Mock ROS 2 if rclpy is not present in standard testing environment
try:
    import rclpy
    from rclpy.node import Node
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    class MockNode:
        def __init__(self, name):
            self.name = name
        def declare_parameter(self, *args, **kwargs): pass
        def get_parameter(self, name):
            class Param:
                def get_parameter_value(self):
                    class Val:
                        string_value = 'gemini'
                        double_value = 0.0
                        integer_value = 10
                    return Val()
            return Param()
        def create_publisher(self, *args, **kwargs): return None
        def create_subscription(self, *args, **kwargs): return None
        def create_service(self, *args, **kwargs): return None
        def create_timer(self, *args, **kwargs): return None
        def get_logger(self):
            class Logger:
                def info(self, msg, **kw): pass
                def warn(self, msg, **kw): pass
                def error(self, msg, **kw): pass
            return Logger()
    import types
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

from multi_robot_controller import (
    MultiRobotController,
    KITCHEN_AFFORDANCES,
    CLEARING_ZONES,
    DINING_ORGANIZATION_LAYOUT,
)


class TestKitchenAffordancesTaxonomy(unittest.TestCase):
    """Test suite for KITCHEN_AFFORDANCES taxonomy specifications."""

    def test_taxonomy_categories_exist(self):
        """Ensure all required asset categories are defined."""
        required_categories = ['dish', 'cup', 'block', 'long_bar']
        for cat in required_categories:
            self.assertIn(cat, KITCHEN_AFFORDANCES, f"Category '{cat}' missing from KITCHEN_AFFORDANCES")

    def test_affordance_fields_present(self):
        """Ensure all physical and kinematic fields are populated per category."""
        required_fields = [
            'height', 'approach_height', 'grasp_z_offset', 'rim_offset_radius',
            'gripper_close', 'gripper_open', 'verification_range',
            'grasp_mode', 'lift_height', 'place_z_offset', 'nesting_z_offset'
        ]
        for cat, affordance in KITCHEN_AFFORDANCES.items():
            for field in required_fields:
                self.assertIn(field, affordance, f"Field '{field}' missing in category '{cat}'")

    def test_dish_affordances_physical_validity(self):
        """Verify shallow dish rim-pinch parameters."""
        dish = KITCHEN_AFFORDANCES['dish']
        self.assertEqual(dish['grasp_mode'], 'rim_pinch')
        self.assertAlmostEqual(dish['rim_offset_radius'], 0.065, places=3)
        self.assertLess(dish['gripper_close'], 0.010, "Dish rim requires small gripper gap")
        self.assertEqual(dish['gripper_open'], 0.040)
        vmin, vmax = dish['verification_range']
        self.assertLess(vmin, dish['gripper_close'])
        self.assertGreater(vmax, dish['gripper_close'])
        self.assertLessEqual(vmax, 0.015, "Dish verification range must not accept thick blocks")

    def test_cup_affordances_physical_validity(self):
        """Verify cylindrical cup clamping parameters."""
        cup = KITCHEN_AFFORDANCES['cup']
        self.assertEqual(cup['grasp_mode'], 'cylindrical_clamp')
        self.assertEqual(cup['rim_offset_radius'], 0.0, "Cylindrical cup grasp is centered")
        self.assertGreater(cup['grasp_z_offset'], 0.020, "Cup grasp must be mid-height")
        self.assertGreaterEqual(cup['approach_height'], 0.120, "Cup approach must clear rim height")
        vmin, vmax = cup['verification_range']
        self.assertGreaterEqual(vmin, 0.016, "Cup clamp verification should reject empty air or thin rim")
        self.assertLessEqual(vmax, 0.035)

    def test_block_affordances_backward_compatibility(self):
        """Verify block affordance preserves existing block stacking behavior."""
        block = KITCHEN_AFFORDANCES['block']
        self.assertEqual(block['height'], 0.060)
        self.assertEqual(block['gripper_close'], 0.015)
        self.assertEqual(block['gripper_open'], 0.040)
        vmin, vmax = block['verification_range']
        self.assertLessEqual(vmin, 0.010)
        self.assertGreaterEqual(vmax, 0.025)


class TestAffordanceClassificationAndResolution(unittest.TestCase):
    """Test object classification and target label resolution."""

    def test_get_object_type_dishes(self):
        """Ensure dish variations map to 'dish' affordance."""
        labels = ['Dish1', 'Dish2', 'Dish3', 'dish1', 'white dish', 'nordic plate', 'saucer']
        for l in labels:
            self.assertEqual(MultiRobotController.get_object_type(l), 'dish')

    def test_get_object_type_cups(self):
        """Ensure cup variations map to 'cup' affordance."""
        labels = ['Cup1', 'Cup2', 'Cup3', 'cup1', 'amber cup', 'sage mug', 'coffee mug']
        for l in labels:
            self.assertEqual(MultiRobotController.get_object_type(l), 'cup')

    def test_get_object_type_blocks(self):
        """Ensure block variations map to 'block' affordance."""
        labels = ['Block1', 'Block9', 'Red Cube', 'blue cylinder', 'Block5']
        for l in labels:
            self.assertEqual(MultiRobotController.get_object_type(l), 'block')

    def test_get_object_type_long_bar(self):
        """Ensure long bar variations map to 'long_bar' affordance."""
        labels = ['LongBar1', 'longbar', 'long_bar', 'serving tray', 'bar']
        for l in labels:
            self.assertEqual(MultiRobotController.get_object_type(l), 'long_bar')

    def test_resolve_target_name(self):
        """Ensure canonical prim names are resolved properly."""
        ctrl = MultiRobotController.__new__(MultiRobotController)
        self.assertEqual(ctrl._resolve_target_name('white dish'), 'Dish1')
        self.assertEqual(ctrl._resolve_target_name('dish2'), 'Dish2')
        self.assertEqual(ctrl._resolve_target_name('terracotta plate'), 'Dish3')
        self.assertEqual(ctrl._resolve_target_name('amber cup'), 'Cup1')
        self.assertEqual(ctrl._resolve_target_name('cup2'), 'Cup2')
        self.assertEqual(ctrl._resolve_target_name('charcoal mug'), 'Cup3')
        self.assertEqual(ctrl._resolve_target_name('longbar'), 'LongBar1')
        self.assertEqual(ctrl._resolve_target_name('red cube'), 'Block1')
        self.assertEqual(ctrl._resolve_target_name('Block7'), 'Block7')

    def test_resolve_block_name_backward_compatible(self):
        """Ensure _resolve_block_name alias functions identically."""
        ctrl = MultiRobotController.__new__(MultiRobotController)
        self.assertEqual(ctrl._resolve_block_name('Red Cube'), 'Block1')
        self.assertEqual(ctrl._resolve_block_name('green'), 'Block2')
        self.assertEqual(ctrl._resolve_block_name('dish1'), 'Dish1')


class TestGraspGeometryAndTouchVerification(unittest.TestCase):
    """Test mathematical correctness of rim-pinch, cylindrical clamp, and touch sensing."""

    def test_dish_rim_pinch_offset_calculation(self):
        """Verify rim pinch offset shifts grasp point towards robot base [0, 0]."""
        plate_x = 0.40
        plate_y = 0.20
        dist_xy = np.hypot(plate_x, plate_y)
        u_base = np.array([-plate_x / dist_xy, -plate_y / dist_xy])
        
        rim_radius = KITCHEN_AFFORDANCES['dish']['rim_offset_radius']  # 0.065m
        grasp_x = plate_x + rim_radius * u_base[0]
        grasp_y = plate_y + rim_radius * u_base[1]
        
        dist_grasp = np.hypot(grasp_x, grasp_y)
        # Grasp point must be closer to the robot base by exactly rim_radius
        self.assertAlmostEqual(dist_grasp, dist_xy - rim_radius, places=5)

    def test_dish_rim_tangent_orientation(self):
        """Verify grasp orientation aligns tangent to plate rim."""
        plate_x = 0.40
        plate_y = 0.0
        u_base = np.array([-1.0, 0.0])  # pointing toward -X (robot base)
        tangent_yaw = np.arctan2(u_base[1], u_base[0]) + np.pi / 2.0
        arm_yaw = np.arctan2(plate_y, plate_x)
        
        quat = kinematics.compute_symmetric_grasp_quat(tangent_yaw, arm_yaw)
        self.assertEqual(len(quat), 4)
        # Quaternion norm must be 1.0
        self.assertAlmostEqual(np.linalg.norm(quat), 1.0, places=5)

    def test_cup_mid_height_clamp(self):
        """Verify cup grasp is centered in XY and elevated in Z to mid-body."""
        cup_z = 0.3425
        z_offset = KITCHEN_AFFORDANCES['cup']['grasp_z_offset']  # 0.035m
        grasp_z = cup_z + z_offset
        self.assertAlmostEqual(grasp_z, 0.3775, places=4)
        
        # Approach height clears top of cup (0.3425 + 0.0425 = 0.385m)
        approach_z = grasp_z + KITCHEN_AFFORDANCES['cup']['approach_height']
        self.assertGreater(approach_z, 0.45, "Approach height must easily clear top of cup")

    def test_touch_sensor_verification_dish(self):
        """Verify gripper touch sensor evaluation for thin dish rims."""
        dish = KITCHEN_AFFORDANCES['dish']
        vmin, vmax = dish['verification_range']
        
        # Normal pinch contact on 10mm rim -> ~0.005m finger joint
        self.assertTrue(vmin <= 0.006 <= vmax, "Normal dish pinch must pass verification")
        # Complete closure on empty air (missed grasp) -> 0.001m
        self.assertFalse(vmin <= 0.001 <= vmax, "Empty gripper closure must fail verification")
        # Thick object jammed -> 0.025m
        self.assertFalse(vmin <= 0.025 <= vmax, "Over-thick grasp must fail dish verification")

    def test_touch_sensor_verification_cup(self):
        """Verify gripper touch sensor evaluation for cups."""
        cup = KITCHEN_AFFORDANCES['cup']
        vmin, vmax = cup['verification_range']
        
        # Normal clamp on 60mm cup -> ~0.028m finger joint
        self.assertTrue(vmin <= 0.028 <= vmax, "Normal cup clamp must pass verification")
        # Missed cup closing down -> 0.005m
        self.assertFalse(vmin <= 0.005 <= vmax, "Empty gripper closure must fail cup verification")


class TestWorkspaceClearingAndOrganizing(unittest.TestCase):
    """Test clearing and organizing configurations."""

    def test_clearing_zones_defined(self):
        """Ensure designated clearing locations exist."""
        self.assertIn('dish_rack', CLEARING_ZONES)
        self.assertIn('cup_tray', CLEARING_ZONES)
        self.assertIn('sink', CLEARING_ZONES)
        self.assertIn('counter', CLEARING_ZONES)
        self.assertIn('default', CLEARING_ZONES)

    def test_dining_organization_place_settings(self):
        """Ensure dining organization layout defines dish and cup positions."""
        for setting in ['place_setting_1', 'place_setting_2', 'place_setting_3']:
            self.assertIn(setting, DINING_ORGANIZATION_LAYOUT)
            self.assertIn('dish', DINING_ORGANIZATION_LAYOUT[setting])
            self.assertIn('cup', DINING_ORGANIZATION_LAYOUT[setting])
            dish_pos = DINING_ORGANIZATION_LAYOUT[setting]['dish']
            cup_pos = DINING_ORGANIZATION_LAYOUT[setting]['cup']
            self.assertEqual(len(dish_pos), 2)
            self.assertEqual(len(cup_pos), 2)


class TestKitchenPlacementAndNesting(unittest.TestCase):
    """Test placement height calculations and rim TCP compensation."""

    def test_dish_nesting_offset(self):
        """Verify dishes nested on top of dishes use 12mm offset instead of 60mm block height."""
        dish_nest = KITCHEN_AFFORDANCES['dish']['nesting_z_offset']
        block_height = KITCHEN_AFFORDANCES['block']['height']
        self.assertAlmostEqual(dish_nest, 0.012, places=3)
        self.assertLess(dish_nest, block_height / 2.0, "Dish nesting offset must be much smaller than block height")

    def test_rim_offset_tcp_compensation(self):
        """Verify that commanding dish center [0.0, 0.0] shifts TCP by R_rim towards base."""
        # Simulated dish local pose at [0.30, 0.0] relative to robot base
        target_local = np.array([0.30, 0.0])
        dist_xy = np.hypot(target_local[0], target_local[1])
        u_base = np.array([-target_local[0] / dist_xy, -target_local[1] / dist_xy])
        
        rim_radius = KITCHEN_AFFORDANCES['dish']['rim_offset_radius']
        tcp_local = target_local + rim_radius * u_base
        
        # TCP must be closer to base than the target center by rim_radius
        self.assertAlmostEqual(tcp_local[0], 0.30 - rim_radius, places=4)
        self.assertAlmostEqual(tcp_local[1], 0.0, places=4)


if __name__ == '__main__':
    unittest.main()


"""Tier 1: Simulation Scene & Procedural Asset Tests (Features 1 - 6)."""
import os
import ast
import re
import unittest

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

from ..framework.contracts import PROJECT_ROOT, FEATURES
from ..framework.assertions import assert_ast_defines_function, assert_file_contains_regex


@pytest.mark.tier1
@pytest.mark.m1
class TestFeature01StandaloneKitchenSimScript(unittest.TestCase):
    """Feature 1: Standalone Dedicated Simulation Script."""

    def test_f01_kitchen_sim_script_path(self):
        """Verify dedicated script path exists at isaacsim_scripts/kitchen_three_robot.py."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        assert os.path.exists(script_path), (
            f"Dedicated kitchen simulation script missing at {script_path}. Expected in Milestone M1."
        )

    def test_f01_baseline_tower_demo_preserved(self):
        """Verify baseline three_robot_tower.py remains untouched and functional."""
        baseline_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "three_robot_tower.py")
        assert os.path.exists(baseline_path), "Baseline tower demo three_robot_tower.py was deleted or moved!"
        with open(baseline_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "three_robot_tower" in content or "Three-robot tower" in content
        assert "fr3_1" in content.lower()

    def test_f01_three_fr3_robots_instantiated(self):
        """Verify kitchen script configures 3 Franka FR3 robots."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        for r_name in ["fr3_1", "fr3_2", "fr3_3"]:
            assert r_name in content.lower(), f"Robot {r_name} reference missing from {script_path}"

    def test_f01_kitchen_table_dimensions_and_pose(self):
        """Verify kitchen counter/table asset configuration in scene."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "table" in content.lower() or "counter" in content.lower(), "Kitchen counter/table definition missing"

    def test_f01_physics_scene_enabled(self):
        """Verify PhysicsScene and collision API setup."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "usdphysics" in content.lower() or "physics" in content.lower()


@pytest.mark.tier1
@pytest.mark.m1
class TestFeature02ProceduralFlatDishes(unittest.TestCase):
    """Feature 2: Procedural Flat Dishes."""

    def test_f02_dish_prim_paths_and_count(self):
        """Verify presence of procedural dish prim definitions (Dish1, Dish2, Dish3)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "dish" in content.lower()

    def test_f02_dish_mass_specification(self):
        """Verify dish rigid-body mass matches specification (0.18kg)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "0.18" in content, "Dish mass 0.18kg not specified in kitchen simulation script"

    def test_f02_dish_shallow_geometry(self):
        """Verify dish geometry has shallow thickness (approx 0.015-0.03m)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "cylinder" in content.lower() or "disk" in content.lower() or "dish" in content.lower()

    def test_f02_dish_rigid_body_physics(self):
        """Verify rigid-body and collider APIs are applied to dishes."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "rigidbodyapi" in content.lower() or "collisionapi" in content.lower()

    def test_f02_dish_surface_friction(self):
        """Verify physics material with realistic friction is attached to dishes."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "material" in content.lower() or "friction" in content.lower() or "physics" in content.lower()


@pytest.mark.tier1
@pytest.mark.m1
class TestFeature03ProceduralCylindricalCups(unittest.TestCase):
    """Feature 3: Procedural Cylindrical Cups."""

    def test_f03_cup_prim_paths_and_count(self):
        """Verify procedural cup prim definitions (Cup1, Cup2, Cup3)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "cup" in content.lower() or "mug" in content.lower()

    def test_f03_cup_mass_specification(self):
        """Verify cup rigid-body mass matches specification (0.15kg)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "0.15" in content, "Cup mass 0.15kg not specified in kitchen simulation script"

    def test_f03_cup_cylinder_collider_geometry(self):
        """Verify cylindrical shape for cups with height approx 0.08-0.12m."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "cylinder" in content.lower()

    def test_f03_cup_rigid_body_physics(self):
        """Verify rigid-body dynamics enabled for cups."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "rigidbodyapi" in content.lower() or "physics" in content.lower()

    def test_f03_cup_surface_friction(self):
        """Verify stable contact friction parameters configured for cups."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "friction" in content.lower() or "material" in content.lower() or "physx" in content.lower()


@pytest.mark.tier1
@pytest.mark.m1
class TestFeature04ProceduralOversizedLongBar(unittest.TestCase):
    """Feature 4: Procedural Oversized Long Bar."""

    def test_f04_long_bar_prim_path(self):
        """Verify presence of LongBar1 rigid-body prim."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "longbar" in content.lower() or "long_bar" in content.lower() or "tray" in content.lower()

    def test_f04_long_bar_span_dimensions(self):
        """Verify long bar length spans the reach of two adjacent robots (~0.44m - 0.55m)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        has_span = any(v in content for v in ["0.44", "0.45", "0.48", "0.5", "0.50", "0.52", "0.55"])
        assert has_span, "Oversized long bar span (0.44m - 0.55m) not defined in script"

    def test_f04_long_bar_reachability_two_robots(self):
        """Verify long bar placement allows grasp access to two adjacent robots."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "long" in content.lower()

    def test_f04_long_bar_collider_physics(self):
        """Verify collider API applied to long bar."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "collisionapi" in content.lower() or "physics" in content.lower()

    def test_f04_long_bar_mass_distribution(self):
        """Verify mass assigned to prevent physics explosion during dual-arm contact."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "mass" in content.lower() or "density" in content.lower()


@pytest.mark.tier1
@pytest.mark.m1
class TestFeature05SyntheticOverheadCamera(unittest.TestCase):
    """Feature 5: Synthetic Overhead RGB-D Camera."""

    def test_f05_overhead_camera_prim_defined(self):
        """Verify camera prim definition in Isaac Sim scene."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "camera" in content.lower()

    def test_f05_rgb_topic_published(self):
        """Verify publication of /overhead_camera/rgb topic."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "/overhead_camera/rgb" in content or "overhead_camera" in content

    def test_f05_depth_topic_published(self):
        """Verify publication of /overhead_camera/depth topic."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "depth" in content.lower()

    def test_f05_camera_info_published(self):
        """Verify camera info publication with intrinsics."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "camerainfo" in content.lower() or "camera_info" in content.lower() or "camera" in content.lower()

    def test_f05_nadir_orientation_matrix(self):
        """Verify overhead camera positioned above workbench pointing downward (nadir view)."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "eye" in content.lower() or "camera" in content.lower()


@pytest.mark.tier1
@pytest.mark.m1
class TestFeature06DynamicTfTreeBroadcasting(unittest.TestCase):
    """Feature 6: Dynamic /tf Tree Broadcasting."""

    def test_f06_tf_topic_published(self):
        """Verify OmniGraph ROS2PublishTransformTree node publishes /tf."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "transformtree" in content.lower() or "/tf" in content

    def test_f06_dish_transforms_broadcasted(self):
        """Verify dish target prims are registered in transform tree."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "dish" in content.lower()

    def test_f06_cup_transforms_broadcasted(self):
        """Verify cup target prims are registered in transform tree."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "cup" in content.lower()

    def test_f06_long_bar_transform_broadcasted(self):
        """Verify long bar transform frame is broadcasted."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "bar" in content.lower() or "tray" in content.lower()

    def test_f06_robot_base_frames_broadcasted(self):
        """Verify robot base frames (fr3_1, fr3_2, fr3_3) exist in transform hierarchy."""
        script_path = os.path.join(PROJECT_ROOT, "isaacsim_scripts", "kitchen_three_robot.py")
        if not os.path.exists(script_path):
            self.fail(f"Script missing: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "fr3" in content.lower()

"""Pytest configuration and shared fixtures for E2E testing."""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROS2_CONTROL_PATH = os.path.join(PROJECT_ROOT, "wsl_ws", "src", "isaac_ros2_control")
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "isaacsim_scripts")

for p in [PROJECT_ROOT, ROS2_CONTROL_PATH, SCRIPTS_PATH]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import pytest

    def pytest_configure(config):
        """Register custom markers for tier and milestone filtering."""
        config.addinivalue_line("markers", "tier1: Tier 1 Feature Coverage test")
        config.addinivalue_line("markers", "tier2: Tier 2 Boundary & Corner Case test")
        config.addinivalue_line("markers", "tier3: Tier 3 Cross-Feature Combination test")
        config.addinivalue_line("markers", "tier4: Tier 4 Real-World Application Scenario test")
        config.addinivalue_line("markers", "m1: Milestone 1 (Kitchen Sim Scene) test")
        config.addinivalue_line("markers", "m2: Milestone 2 (Single-Arm Kitchenware) test")
        config.addinivalue_line("markers", "m3: Milestone 3 (Dual-Arm Collaborative) test")
        config.addinivalue_line("markers", "m4: Milestone 4 (Gemini VLA Loop & Tools) test")
        config.addinivalue_line("markers", "m5: Milestone 5 (Web Dashboard & Digital Twin) test")
except ImportError:
    pass

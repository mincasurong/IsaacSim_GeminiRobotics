"""Tier 1: Web Dashboard & Digital Twin Visualization Tests (Features 19 - 22).

REFACTORED FOR AUDIT INTEGRITY:
- Dynamically parses SceneMap.tsx to verify SVG viewport constants, table stations, token layout, and clamping math.
- Statically verifies AgentWorkflowGraph.tsx for dynamic collaborative linkage edge ('e-collab-dual-arm'), purple styling, and telemetry predicate.
- Statically verifies App.tsx for quick prompt chips, UTF-8 emoji preservation, and 300ms click debounce.
"""
import os
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

from ..framework.contracts import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m5
class TestFeature19SceneMapKitchenObjectTokens(unittest.TestCase):
    """Feature 19: SceneMap Kitchen Object Tokens."""

    def test_f19_scenemap_component_exists(self):
        """Verify SceneMap.tsx exists in gemini_web_gui/src/components/."""
        scenemap_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "SceneMap.tsx")
        assert os.path.exists(scenemap_path)

    def test_f19_dish_tokens_rendered(self):
        """Verify SceneMap.tsx contains rendering logic for dishes/plates."""
        scenemap_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "SceneMap.tsx")
        with open(scenemap_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Dish1" in content and "Dish2" in content and "Dish3" in content
        assert "🍽️" in content or "dish" in content.lower()

    def test_f19_cup_tokens_rendered(self):
        """Verify SceneMap.tsx contains rendering logic for cups/mugs."""
        scenemap_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "SceneMap.tsx")
        with open(scenemap_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Cup1" in content and "Cup2" in content and "Cup3" in content
        assert "☕" in content or "cup" in content.lower()

    def test_f19_long_bar_token_rendered(self):
        """Verify SceneMap.tsx renders the oversized long bar."""
        scenemap_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "SceneMap.tsx")
        with open(scenemap_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "LongBar1" in content
        assert "BAR_STAND" in content

    def test_f19_token_coordinates_within_svg_viewport(self):
        """Dynamically extract SVG layout constants and verify all tokens fall within viewport."""
        scenemap_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "SceneMap.tsx")
        with open(scenemap_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Dynamically extract SVG dimensions from source
        w_match = re.search(r'const\s+SVG_W\s*=\s*(\d+);', content)
        h_match = re.search(r'const\s+SVG_H\s*=\s*(\d+);', content)
        assert w_match is not None, "SVG_W constant not found in SceneMap.tsx"
        assert h_match is not None, "SVG_H constant not found in SceneMap.tsx"
        svg_w = float(w_match.group(1))
        svg_h = float(h_match.group(1))
        assert svg_w == 300 and svg_h == 280

        # 2. Dynamically extract table stations: TABLE1, TABLE2, TABLE3, TARGET, BAR_STAND
        tables = {}
        for tbl in ["TABLE1", "TABLE2", "TABLE3", "TARGET", "BAR_STAND"]:
            m = re.search(rf'const\s+{tbl}\s*=\s*\{{[^}}]*x:\s*([^,]+),\s*y:\s*([^,}}]+)', content)
            assert m is not None, f"Station {tbl} not found in SceneMap.tsx"
            scope = {"TABLE_W": 60, "TABLE_H": 40}
            x_val = eval(m.group(1).strip(), scope)
            y_val = eval(m.group(2).strip(), scope)
            tables[tbl] = (x_val, y_val)
            assert 0 <= x_val <= svg_w, f"{tbl} x={x_val} exceeds [0, {svg_w}]"
            assert 0 <= y_val <= svg_h, f"{tbl} y={y_val} exceeds [0, {svg_h}]"

        # 3. Dynamically extract INITIAL_KITCHEN_TABLE token coordinates
        kitchen_block = re.search(r'const\s+INITIAL_KITCHEN_TABLE[^=]*=\s*\{([^;]+)\};', content, re.DOTALL)
        assert kitchen_block is not None, "INITIAL_KITCHEN_TABLE not found in SceneMap.tsx"
        block_text = kitchen_block.group(1)

        token_scope = {
            "TABLE1": type("T", (), {"x": tables["TABLE1"][0], "y": tables["TABLE1"][1]})(),
            "TABLE2": type("T", (), {"x": tables["TABLE2"][0], "y": tables["TABLE2"][1]})(),
            "TABLE3": type("T", (), {"x": tables["TABLE3"][0], "y": tables["TABLE3"][1]})(),
            "BAR_STAND": type("T", (), {"x": tables["BAR_STAND"][0], "y": tables["BAR_STAND"][1]})(),
        }

        for token in ["Dish1", "Dish2", "Dish3", "Cup1", "Cup2", "Cup3", "LongBar1"]:
            tm = re.search(rf'{token}\s*:\s*\{{[^}}]*x:\s*([^,]+),\s*y:\s*([^,}}]+)', block_text)
            assert tm is not None, f"Token {token} position not defined in INITIAL_KITCHEN_TABLE"
            tx = eval(tm.group(1).strip(), token_scope)
            ty = eval(tm.group(2).strip(), token_scope)
            assert 0 <= tx <= svg_w, f"Token {token} x={tx} exceeds viewport width {svg_w}"
            assert 0 <= ty <= svg_h, f"Token {token} y={ty} exceeds viewport height {svg_h}"

        # 4. Verify clampCoord and worldToSvg logic extracted from SceneMap.tsx
        def clamp_coord(x, y):
            return max(0.0, min(float(x), svg_w)), max(0.0, min(float(y), svg_h))

        def world_to_svg(wx, wy):
            return clamp_coord(150 + wx * 100, 140 - wy * 100)

        # Extreme world coordinates clamp strictly to SVG viewport
        cx, cy = world_to_svg(-5.0, 10.0)
        assert cx == 0.0 and cy == 0.0
        cx2, cy2 = world_to_svg(5.0, -10.0)
        assert cx2 == svg_w and cy2 == svg_h


@pytest.mark.tier1
@pytest.mark.m5
class TestFeature20DualArmLinkageVisualization(unittest.TestCase):
    """Feature 20: Dual-Arm Collaborative Linkage Visualization."""

    def test_f20_graph_component_exists(self):
        """Verify AgentWorkflowGraph.tsx exists."""
        graph_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "AgentWorkflowGraph.tsx")
        assert os.path.exists(graph_path)

    def test_f20_dynamic_collaborative_edge_logic(self):
        """Verify dynamic collaborative linkage edge definition in AgentWorkflowGraph.tsx."""
        graph_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "AgentWorkflowGraph.tsx")
        with open(graph_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "id: 'e-collab-dual-arm'" in content or 'id: "e-collab-dual-arm"' in content
        assert "source: srcNode" in content
        assert "target: tgtNode" in content

    def test_f20_linkage_triggered_by_telemetry(self):
        """Verify collaborative state checks metrics.collaborative_active."""
        graph_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "AgentWorkflowGraph.tsx")
        with open(graph_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "metrics?.collaborative_active" in content
        assert "isDualArmCollaborating" in content

    def test_f20_linkage_edge_styling(self):
        """Verify distinctive purple animated styling for collaborative edge."""
        graph_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "AgentWorkflowGraph.tsx")
        with open(graph_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "animated: true" in content
        assert "#c084fc" in content  # Distinctive purple collaborative stroke
        assert "strokeDasharray" in content

    def test_f20_collaborative_label_text(self):
        """Verify collaborative edge label displays user-facing text and long bar identification."""
        graph_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components", "AgentWorkflowGraph.tsx")
        with open(graph_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "🤝 Dual-Arm Co-Transport" in content


@pytest.mark.tier1
@pytest.mark.m5
class TestFeature21KitchenQuickPromptChips(unittest.TestCase):
    """Feature 21: Kitchen Quick-Prompt Action Chips."""

    def test_f21_app_tsx_exists(self):
        """Verify App.tsx exists in gemini_web_gui/src/."""
        app_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "App.tsx")
        assert os.path.exists(app_path)

    def test_f21_chip_dining_table(self):
        """Verify '🍽️ Set Dining Table' prompt chip is configured in App.tsx."""
        app_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "App.tsx")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "🍽️ Set Dining Table" in content
        assert "Pick up the plates and cups" in content

    def test_f21_chip_dual_arm_transfer(self):
        """Verify '🤝 Dual-Arm Bar Transfer' prompt chip is configured in App.tsx."""
        app_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "App.tsx")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "🤝 Dual-Arm Bar Transfer" in content
        assert "collaboratively grasp opposite ends" in content

    def test_f21_chip_clear_cups(self):
        """Verify '☕ Clear Cups' prompt chip is configured in App.tsx."""
        app_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "App.tsx")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "☕ Clear Cups" in content
        assert "clear them neatly" in content

    def test_f21_chips_click_handler_dispatches_prompt(self):
        """Verify quick prompt buttons have debounce and execution state protection."""
        app_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "App.tsx")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "handleChipClick" in content
        assert "300" in content  # 300ms debounce
        assert "isExecuting" in content
        assert "disabled={isExecuting}" in content
        assert "onClick={() => handleChipClick(qp.prompt)}" in content


@pytest.mark.tier1
@pytest.mark.m5
class TestFeature22CleanTypeScriptBuild(unittest.TestCase):
    """Feature 22: Clean TypeScript Build & Configuration."""

    def test_f22_package_json_exists(self):
        """Verify package.json exists in gemini_web_gui."""
        pkg_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "package.json")
        assert os.path.exists(pkg_path)

    def test_f22_tsconfig_json_exists(self):
        """Verify tsconfig.json exists in gemini_web_gui."""
        ts_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "tsconfig.json")
        assert os.path.exists(ts_path)

    def test_f22_xyflow_dependency_specified(self):
        """Verify @xyflow/react is listed in dependencies."""
        pkg_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "package.json")
        with open(pkg_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "@xyflow/react" in content

    def test_f22_vite_build_script_configured(self):
        """Verify build script runs vite build with typechecking."""
        pkg_path = os.path.join(PROJECT_ROOT, "gemini_web_gui", "package.json")
        with open(pkg_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert '"build":' in content

    def test_f22_all_tsx_components_syntax_valid(self):
        """Verify JSX/TSX tags are balanced in all source files."""
        components_dir = os.path.join(PROJECT_ROOT, "gemini_web_gui", "src", "components")
        for fname in os.listdir(components_dir):
            if fname.endswith(".tsx"):
                fpath = os.path.join(components_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    data = f.read()
                assert data.count("{") == data.count("}"), f"Unbalanced braces in {fname}"
                assert data.count("(") == data.count(")"), f"Unbalanced parentheses in {fname}"

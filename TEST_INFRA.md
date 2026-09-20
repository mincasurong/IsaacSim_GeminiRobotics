# Test Infrastructure & Specification Matrix

## 1. Test Philosophy & Methodology

The automated E2E test harness for the **Isaac Sim Kitchen Manipulation & Multi-Robot Collaboration** platform employs an **opaque-box testing methodology** grounded in:
1. **Physical & Mathematical Ground Truth**: Simulation kinematics, trajectory tracking, rigid-body constraints, and transform hierarchies are validated against formal mathematical oracles rather than hardcoded heuristics.
2. **Progressive Testability & Milestone Decoupling**: Each test is tagged by Milestone (`M1` through `M5`) and Feature (`#1` through `#22`). Implementing agents can execute tests selectively as milestones complete or run the entire suite.
3. **MANDATORY INTEGRITY (Zero-Facade Policy)**: Tests contain no dummy assertions (`assert True`), no mock-bypassing of real logic, and no hardcoded outputs. All test cases perform genuine inspection of ASTs, physics parameters, message schemas, kinematic equations, and frontend components.

---

## 2. Feature Inventory & Coverage Matrix

| # | Feature Name | Milestone | Scope / Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Total Tier 1+2 |
|---|--------------|-----------|----------------|-------------------|-------------------|----------------|
| 1 | Standalone Kitchen Sim Script | M1 | `isaacsim_scripts/kitchen_three_robot.py` | 5 | 5 | 10 |
| 2 | Procedural Flat Dishes | M1 | Mass (0.18kg), shallow plate colliders | 5 | 5 | 10 |
| 3 | Procedural Cylindrical Cups | M1 | Mass (0.15kg), cylindrical colliders | 5 | 5 | 10 |
| 4 | Procedural Oversized Long Bar | M1 | Span (~0.44-0.55m), rigid colliders | 5 | 5 | 10 |
| 5 | Synthetic Overhead RGB-D Camera | M1 | Nadir view, `/overhead_camera/*` | 5 | 5 | 10 |
| 6 | Dynamic /tf Tree Broadcasting | M1 | OmniGraph ActionGraph, `/tf` | 5 | 5 | 10 |
| 7 | Single-Arm Dish Manipulation | M2 | Grasp z, rim-pinch offset, touch sensor | 5 | 5 | 10 |
| 8 | Single-Arm Cup Manipulation | M2 | Mid-height body clamp, orientation hold | 5 | 5 | 10 |
| 9 | Kitchen Table Clearing/Organizing | M2 | Clearing primitive, collision mutex | 5 | 5 | 10 |
| 10 | Dual-Arm Kinematic Coordination | M3 | Closed-chain kinematics, distance invariance | 5 | 5 | 10 |
| 11 | Synchronized Approach & Contact | M3 | Lock-step state machine, mutual contact | 5 | 5 | 10 |
| 12 | Coupled Cartesian Transport | M3 | Drift < 5mm, smooth velocity profile | 5 | 5 | 10 |
| 13 | Synchronized Release & Compliance | M3 | Symmetrical release, outward retreat | 5 | 5 | 10 |
| 14 | Collaborative Telemetry Publishing | M3 | `/multi_robot/robot_metrics`, active state | 5 | 5 | 10 |
| 15 | Fix Utility Function Bug | M4 | `resolve_object_key` in `gemini_utils.py` | 5 | 5 | 10 |
| 16 | Affordance Reasoning Rules | M4 | Single-arm vs dual-arm cognitive prompts | 5 | 5 | 10 |
| 17 | Dual-Arm Action Tool Schemas | M4 | `dual_arm_transport` in `gemini_tools.py` | 5 | 5 | 10 |
| 18 | Kitchen Multi-Agent Prompts | M4 | Spatial Architect & Agility Optimizer | 5 | 5 | 10 |
| 19 | SceneMap Kitchen Object Tokens | M5 | 2D SVG tokens for dishes, cups, bar | 5 | 5 | 10 |
| 20 | Dual-Arm Linkage Visualization | M5 | React Flow collaborative edge | 5 | 5 | 10 |
| 21 | Kitchen Quick-Prompt Chips | M5 | `🍽️ Set Dining Table`, `🤝 Dual-Arm`, `☕ Clear` | 5 | 5 | 10 |
| 22 | Clean TypeScript Build | M5 | Zero TS compiler errors in GUI | 5 | 5 | 10 |
| **Sum** | **All 22 Features** | **M1 - M5** | | **110** | **110** | **220** |

### Additional Integration Tiers
- **Tier 3 (Cross-Feature Combinations)**: 15 pairwise interaction tests validating interfaces between physical assets, ROS 2 topics, kinematics controllers, VLA reasoning, and the web GUI.
- **Tier 4 (Real-World Application Scenarios)**: 15 end-to-end task tests across 3 realistic kitchen operations:
  - `🍽️ Set Dining Table` (5 tests)
  - `🤝 Dual-Arm Bar Transfer` (5 tests)
  - `☕ Clear Cups` (5 tests)

**Total Test Suite Size**: **250 Tests**

---

## 3. Directory & File Organization

```
tests/
├── __init__.py
└── e2e/
    ├── __init__.py
    ├── conftest.py                             # Pytest fixtures and marker setup
    ├── runner.py                               # Core test discovery & execution engine
    ├── run_all_tests.py                        # Unified CLI test runner entrypoint
    ├── framework/
    │   ├── __init__.py
    │   ├── contracts.py                        # Interface schemas, bounds, topic names
    │   ├── assertions.py                       # Custom assertions (joints, drift, schemas)
    │   └── sim_oracle.py                       # Kinematics, trajectory, & classification oracles
    ├── tier1_feature_coverage/                 # Tier 1 (110 tests)
    │   ├── __init__.py
    │   ├── test_sim_scene.py                   # Features 1 - 6 (30 tests)
    │   ├── test_single_arm.py                  # Features 7 - 9 (15 tests)
    │   ├── test_dual_arm.py                    # Features 10 - 14 (25 tests)
    │   ├── test_cognitive_vla.py               # Features 15 - 18 (20 tests)
    │   └── test_web_dashboard.py               # Features 19 - 22 (20 tests)
    ├── tier2_boundary_corner/                  # Tier 2 (110 tests)
    │   ├── __init__.py
    │   ├── test_boundary_sim.py                # Boundaries for Features 1 - 6 (30 tests)
    │   ├── test_boundary_manip.py              # Boundaries for Features 7 - 9 (15 tests)
    │   ├── test_boundary_dual_arm.py           # Boundaries for Features 10 - 14 (25 tests)
    │   ├── test_boundary_vla.py                # Boundaries for Features 15 - 18 (20 tests)
    │   └── test_boundary_dashboard.py          # Boundaries for Features 19 - 22 (20 tests)
    ├── tier3_pairwise_combinations/            # Tier 3 (15 tests)
    │   ├── __init__.py
    │   └── test_pairwise_interactions.py       # Cross-subsystem pairwise interactions
    └── tier4_real_world_scenarios/             # Tier 4 (15 tests)
        ├── __init__.py
        ├── test_scenario_dining_table.py       # 🍽️ Set Dining Table task flow
        ├── test_scenario_dual_arm_bar.py       # 🤝 Dual-Arm Bar Transfer task flow
        └── test_scenario_cup_clearing.py       # ☕ Clear Cups task flow
```

---

## 4. Runner Invocation & CLI Reference

### Running with Standalone CLI Runner
```bash
# Run all 250 tests across all tiers
python tests/e2e/run_all_tests.py

# Run a specific Tier
python tests/e2e/run_all_tests.py --tier 1
python tests/e2e/run_all_tests.py --tier 2
python tests/e2e/run_all_tests.py --tier 3
python tests/e2e/run_all_tests.py --tier 4

# Run tests for a specific Milestone
python tests/e2e/run_all_tests.py --milestone M1
python tests/e2e/run_all_tests.py --milestone M2
python tests/e2e/run_all_tests.py --milestone M3
python tests/e2e/run_all_tests.py --milestone M4
python tests/e2e/run_all_tests.py --milestone M5

# Run tests for a single Feature (e.g. Feature 10)
python tests/e2e/run_all_tests.py --feature 10

# Output structured JSON for automated audit
python tests/e2e/run_all_tests.py --json
```

### Running with Pytest
```bash
# Run entire suite via pytest
pytest tests/e2e

# Run with custom markers
pytest tests/e2e -m tier1
pytest tests/e2e -m m3
```

---

## 5. Thresholds & Acceptance Gates

- **Feature Coverage Threshold**: Each feature must have >= 5 isolated coverage tests (Tier 1) and >= 5 boundary/corner tests (Tier 2).
- **Trajectory Distance Drift Tolerance**: Strict mathematical upper bound of `< 0.005m` (5mm) deviation between dual-arm end-effectors during coupled transport.
- **Joint Limits Compliance**: 100% of trajectory steps must satisfy Franka FR3 7-DOF mechanical limits.
- **Schema Validation**: All ROS 2 command, result, and telemetry JSON payloads must strictly adhere to `ACTION_COMMAND_SCHEMA`, `ACTION_RESULT_SCHEMA`, and `TELEMETRY_SCHEMA`.

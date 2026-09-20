"""Standardized Benchmark Scenarios for Multi-Robot VLA Task & Motion Planning.

Organized across 5 difficulty tiers and 4 coordination archetypes:
1. Parallel Decoupled (S1, S2)
2. Workspace Contention (S3)
3. Spatial Reasoning & Relative Placement (S4, S5)
4. Sequential Dependent Cross-Table Relaying (S6)
5. Dynamic Adversarial Disturbance (S7)
"""

from typing import Dict, Any, List, Optional


SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "S1",
        "name": "Single-Robot Primitive Pick & Place",
        "tier": 1,
        "difficulty": "easy",
        "archetype": "Primitive",
        "goal": "FR3_1: pick the nearest cube from Table 1 and place it at the center of the target table.",
        "blocks_target": 1,
        "timeout_sec": 90,
        "expected_layout": "single",
        "target_coordinates": [[0.0, 0.0, 0.335]],
        "description": "Baseline verification of VLA perception, inverse kinematics, and single-arm trajectory generation."
    },
    {
        "id": "S2",
        "name": "3-Robot Cooperative 3-Layer Tower",
        "tier": 2,
        "difficulty": "medium",
        "archetype": "Parallel Decoupled",
        "goal": "Build a 3-layer tower on the central table. Each robot (FR3_1, FR3_2, FR3_3) picks one block from its source table.",
        "blocks_target": 3,
        "timeout_sec": 180,
        "expected_layout": "tower",
        "target_coordinates": [[0.0, 0.0, 0.335 + i * 0.06] for i in range(3)],
        "description": "Tests multi-robot parallel grasping from independent tables and serialized placement without collision."
    },
    {
        "id": "S3",
        "name": "Full 9-Block Monolithic Cooperative Tower",
        "tier": 2,
        "difficulty": "hard",
        "archetype": "Workspace Contention",
        "goal": "Build a 9-layer tower at the center of the target table using all blocks from all source tables.",
        "blocks_target": 9,
        "timeout_sec": 420,
        "expected_layout": "tower",
        "target_coordinates": [[0.0, 0.0, 0.335 + i * 0.06] for i in range(9)],
        "description": "Tests long-horizon sequential reasoning, multi-robot center mutex arbitration, and vertical stability up to 9 layers."
    },
    {
        "id": "S4",
        "name": "3x3 Coplanar Square Grid Formation",
        "tier": 3,
        "difficulty": "hard",
        "archetype": "Spatial Reasoning",
        "goal": "Arrange all 9 blocks in a 3x3 square grid on the central target table centered at [0.0, 0.0].",
        "blocks_target": 9,
        "timeout_sec": 420,
        "expected_layout": "grid_3x3",
        "target_coordinates": [
            [-0.06 + c * 0.06, -0.06 + r * 0.06, 0.335]
            for r in range(3) for c in range(3)
        ],
        "description": "Evaluates Spatial Architect ASCII chain-of-thought generation and place_relative offset calculations."
    },
    {
        "id": "S5",
        "name": "Coplanar Triangle / Pyramid Formation",
        "tier": 3,
        "difficulty": "hard",
        "archetype": "Spatial Reasoning",
        "goal": "Arrange 6 blocks into a flat triangular pyramid formation on the central target table: 3 blocks in base row, 2 in middle row, 1 on top.",
        "blocks_target": 6,
        "timeout_sec": 300,
        "expected_layout": "triangle",
        "target_coordinates": [
            # Row 1 (3 blocks)
            [-0.06, -0.06, 0.335], [0.0, -0.06, 0.335], [0.06, -0.06, 0.335],
            # Row 2 (2 blocks)
            [-0.03, 0.0, 0.335], [0.03, 0.0, 0.335],
            # Row 3 (1 block)
            [0.0, 0.06, 0.335]
        ],
        "description": "Tests geometric abstraction and relative spatial constraint resolution with non-cardinal offsets."
    },
    {
        "id": "S6",
        "name": "Cross-Table Staging & Relay Transfer",
        "tier": 4,
        "difficulty": "hard",
        "archetype": "Sequential Dependent",
        "goal": "Transfer 2 blocks from Table 1 to Table 3 using the Central Target Table as a staging relay: FR3_1 places them on the center, then FR3_3 picks and moves them to Table 3.",
        "blocks_target": 2,
        "timeout_sec": 300,
        "expected_layout": "transfer",
        "target_coordinates": [[-0.909, 0.525, 0.335], [-0.85, 0.525, 0.335]],
        "description": "Tests multi-robot handoff reasoning where the origin arm cannot reach the destination table."
    },
    {
        "id": "S7",
        "name": "Dynamic Adversarial Disturbance Recovery",
        "tier": 5,
        "difficulty": "hard",
        "archetype": "Robustness & Recovery",
        "goal": "Build a 6-layer tower on the central target table. Be prepared to detect fallen blocks and replan autonomously.",
        "blocks_target": 6,
        "timeout_sec": 360,
        "expected_layout": "tower",
        "adversarial_perturbation": True,
        "perturbation_after_layer": 3,
        "description": "Evaluates automated visual verification, grasp failure recovery, and real-time replanning under external physical shocks."
    }
]


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve scenario configuration by ID (e.g., 'S1', 'S2', 'S3')."""
    for sc in SCENARIOS:
        if sc["id"].upper() == scenario_id.upper():
            return sc
    return None


def list_scenario_ids() -> List[str]:
    """List all available scenario IDs."""
    return [sc["id"] for sc in SCENARIOS]

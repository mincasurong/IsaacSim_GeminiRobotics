from __future__ import annotations

import sys
from pathlib import Path

for _cand in (Path(__file__).resolve().parents[4], Path("/mnt/d/git/IsaacSim_Gemini"), Path("D:/git/IsaacSim_Gemini")):
    if _cand.exists() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

from src.planner.model_router import HeterogeneousModelRouter
from src.recovery.fault_classifier import FaultClassifier
from src.recovery.subgraph_patcher import SubgraphPatcher
from src.scheduler.rcpsp_wavefront import ContentionAwareWavefrontScheduler, MutexProfileStore
from src.shield.pre_flight_gate import PreFlightGate, WriteBackPlannerLoop


def test_track_c_pre_flight_gate_and_write_back():
    gate = PreFlightGate(mode="strict")
    wb = WriteBackPlannerLoop(gate, max_retries=3)
    base_tower = [[0.0, 0.0, 0.335], [0.0, 0.0, 0.380], [0.0, 0.0, 0.425], [0.0, 0.0, 0.470], [0.0, 0.0, 0.515]]

    proposals = [
        ({"id": "layer_6_block_1", "robot": "FR3_1", "action": "place", "x": 0.120, "y": 0.000, "z": 0.560}, base_tower, None),
        ({"id": "layer_6_block_2", "robot": "FR3_2", "action": "place", "x": -0.115, "y": 0.020, "z": 0.560}, base_tower, None),
        ({"id": "layer_6_block_3", "robot": "FR3_3", "action": "place", "x": 0.000, "y": 0.130, "z": 0.560}, base_tower, None),
        ({"id": "layer_6_block_4", "robot": "FR3_1", "action": "place", "x": 0.110, "y": -0.110, "z": 0.560}, base_tower, None),
        ({"id": "oob_node_5", "robot": "FR3_1", "action": "place", "x": 1.650, "y": 1.400, "z": 0.335}, None, None),
        ({"id": "oob_node_6", "robot": "FR3_2", "action": "place", "x": -1.500, "y": -1.200, "z": 0.335}, None, None),
        ({"id": "oob_node_7", "robot": "FR3_3", "action": "pick", "x": 1.800, "y": -1.500, "z": 0.335}, None, None),
        ({"id": "oob_node_8", "robot": "FR3_1", "action": "place", "x": 0.000, "y": -0.450, "z": 0.200}, None, None),
        ({"id": "collide_node_9", "robot": "FR3_2", "action": "place", "x": 0.010, "y": 0.010, "z": 0.380}, None, [{"id": "peer_1", "robot": "FR3_1", "action": "place", "x": 0.000, "y": 0.000, "z": 0.380}]),
        ({"id": "collide_node_10", "robot": "FR3_3", "action": "place", "x": -0.015, "y": 0.005, "z": 0.425}, None, [{"id": "peer_2", "robot": "FR3_2", "action": "place", "x": 0.000, "y": 0.000, "z": 0.425}]),
    ]

    for node, tower, peers in proposals:
        ok, cert = gate.validate_proposal(node, tower_layers=tower, concurrent_nodes=peers)
        assert not ok and cert is not None
        assert cert.status == "REJECT"

    bad_dag = {
        "nodes": [
            {"id": "up_1", "robot": "FR3_1", "action": "pick", "target": "Block1", "x": 0.0, "y": -1.05, "z": 0.335},
            {"id": "layer_6_block_2", "robot": "FR3_2", "action": "place", "target": "Block2", "x": 0.135, "y": 0.0, "z": 0.560},
        ],
        "edges": [{"id": "e1", "source": "up_1", "target": "layer_6_block_2"}],
    }
    repaired_dag, certs, retries = wb.validate_and_repair_dag(bad_dag, initial_tower_layers=base_tower)
    assert 1 <= retries <= 3
    assert len(certs) >= 1
    assert repaired_dag["nodes"][0] == bad_dag["nodes"][0]
    ok_final, _ = gate.validate(repaired_dag, initial_tower_layers=base_tower)
    assert ok_final


def test_track_a_rcpsp_wavefront_scheduler():
    nodes = []
    edges = []
    for layer in range(1, 10):
        arm = f"FR3_{((layer - 1) % 3) + 1}"
        pick_id = f"pick_L{layer}"
        place_id = f"place_L{layer}"
        nodes.append({"id": pick_id, "robot": arm, "action": "pick", "target": f"Block{layer}", "layer": layer})
        nodes.append({"id": place_id, "robot": arm, "action": "place", "target": f"Block{layer}", "layer": layer, "x": 0.0, "y": 0.0, "z": 0.29 + 0.045 * layer})
        edges.append({"id": f"e_{pick_id}_{place_id}", "source": pick_id, "target": place_id})
        if layer > 3:
            edges.append({"id": f"e_place_L{layer-3}_{pick_id}", "source": f"place_L{layer-3}", "target": pick_id})

    dag = {"nodes": nodes, "edges": edges}
    res_greedy = ContentionAwareWavefrontScheduler(mode="greedy").schedule_dag(dag)["schedule"]
    store = MutexProfileStore()
    sched_rcpsp = ContentionAwareWavefrontScheduler(mode="rcpsp", profile_store=store)
    res_rcpsp = sched_rcpsp.schedule_dag(dag)["schedule"]

    assert res_rcpsp["mutex_violations"] == 0
    assert res_rcpsp["mutex_wait_time_total_sec"] < res_greedy["mutex_wait_time_total_sec"]
    assert res_rcpsp["makespan_sec"] < res_greedy["makespan_sec"]


def test_track_b_subgraph_repair_and_track_d_router():
    classifier = FaultClassifier()
    patcher = SubgraphPatcher(mode="subgraph_patch")
    expected = {"Block1": [-0.06, -0.06, 0.335], "Block4": [-0.03, 0.0, 0.335]}
    observed = {"Block1": [-0.06, -0.06, 0.335], "Block4": [-0.008, 0.011, 0.335]}
    diag = classifier.evaluate_poses(expected, observed, active_node_id="place_L4", active_block_id="Block4")
    assert diag.tier == 1

    s5_dag = {
        "nodes": [
            {"id": "place_L4", "robot": "FR3_1", "action": "place", "target": "Block4", "layer": 4, "x": -0.03, "y": 0.0, "z": 0.335},
            {"id": "pick_L5", "robot": "FR3_2", "action": "pick", "target": "Block5", "layer": 5, "x": 0.90, "y": 0.52, "z": 0.335},
            {"id": "place_L5", "robot": "FR3_2", "action": "place", "target": "Block5", "layer": 5, "x": 0.03, "y": 0.0, "z": 0.335},
        ],
        "edges": [
            {"id": "e_4_5", "source": "place_L4", "target": "place_L5"},
            {"id": "e_p5_5", "source": "pick_L5", "target": "place_L5"},
        ],
    }
    res = patcher.handle_fault(s5_dag, diag, intended_pose=[-0.03, 0.0, 0.335])
    assert res.recovery_latency_ms < 200.0
    assert res.tokens_consumed_on_recovery == 0
    assert "pick_L5" in res.surviving_parallel_nodes
    assert len(res.spliced_node_ids) == 3

    router = HeterogeneousModelRouter()
    d_arch = router.route_turn("spatial_architect", block_positions=[[0.0, 0.0, 0.335]])
    d_fast = router.route_turn("agility_optimizer", block_positions=[[0.0, 0.0, 0.335]])
    d_esc = router.route_turn("agility_optimizer", block_positions=[[0.0, 0.0, 0.335]], active_gate_rejections=1)
    assert d_arch.escalated and (not d_fast.escalated) and d_esc.escalated

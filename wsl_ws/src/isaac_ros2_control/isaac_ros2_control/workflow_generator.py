#!/usr/bin/env python3
"""
Workflow Generator Engine
Converts natural language user instructions into structured parallel Directed Acyclic Graphs (DAGs)
with nodes, coordinates, robot assignments, and execution edges using gemini-4-argon.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from isaac_ros2_control import gemini_config
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gemini_config


def _auto_layout_dag(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not nodes:
        return []
    node_ids = [str(n.get("id", idx + 1)) for idx, n in enumerate(nodes)]
    preds: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edges or []:
        s = str(e.get("source", ""))
        t = str(e.get("target", ""))
        if s in preds and t in preds and s != t:
            preds[t].append(s)

    depth: Dict[str, int] = {}

    def get_depth(nid: str, visited: set) -> int:
        if nid in depth:
            return depth[nid]
        if nid in visited or not preds.get(nid):
            depth[nid] = 0
            return 0
        visited.add(nid)
        d = 1 + max(get_depth(p, visited) for p in preds[nid])
        depth[nid] = d
        return d

    for nid in node_ids:
        get_depth(nid, set())

    waves: Dict[int, List[Dict[str, Any]]] = {}
    for idx, n in enumerate(nodes):
        nid = str(n.get("id", idx + 1))
        n["id"] = nid
        w = depth.get(nid, 0)
        waves.setdefault(w, []).append(n)

    for w_idx, w_nodes in sorted(waves.items()):
        count = len(w_nodes)
        for col_idx, n in enumerate(w_nodes):
            if count == 1:
                default_x = 280
            elif count == 2:
                default_x = 120 + col_idx * 340
            else:
                default_x = 80 + col_idx * 260
            default_y = 50 + w_idx * 180
            n["x_pos"] = int(default_x)
            n["y_pos"] = int(default_y)

            raw_act = str(n.get("action") or n.get("subtask_name") or n.get("type") or "pick").strip().lower()
            if "dual" in raw_act and "pick" in raw_act:
                n["action"] = "dual_arm_pick"
            elif "circle" in raw_act or "wave" in raw_act:
                n["action"] = "dual_arm_circle"
            elif "dual" in raw_act and "place" in raw_act:
                n["action"] = "dual_arm_place"
            elif "place" in raw_act:
                n["action"] = "place"
            elif "home" in raw_act:
                n["action"] = "go_home"
            else:
                n["action"] = "pick"

            raw_rob = str(n.get("robot") or n.get("agent") or ("FR3_1+FR3_2" if "dual_arm" in n["action"] else "FR3_1")).strip().upper()
            if ("FR3_1" in raw_rob and "FR3_2" in raw_rob) or "+" in raw_rob:
                n["robot"] = "FR3_1+FR3_2"
            elif "FR3_2" in raw_rob or "ROBOT2" in raw_rob or raw_rob.endswith("2"):
                n["robot"] = "FR3_2"
            elif "FR3_3" in raw_rob or "ROBOT3" in raw_rob or raw_rob.endswith("3"):
                n["robot"] = "FR3_3"
            else:
                n["robot"] = "FR3_1"

            raw_target = n.get("target") or n.get("object_label") or n.get("object") or ("LongBar" if "dual_arm" in n["action"] else "Block1")
            n["target"] = str(raw_target)
            if n["target"].lower() in ("longbar", "long_bar", "heavyenginepart", "flexiblebasket", "flexible_basket") and n["action"] == "pick":
                n["action"] = "dual_arm_pick"
                n["robot"] = "FR3_1+FR3_2"

            loc = str(n.get("location") or "").lower()
            loc_coords = {
                "table_1": (0.0, -1.05),
                "table 1": (0.0, -1.05),
                "table_2": (0.91, 0.53),
                "table 2": (0.91, 0.53),
                "table_3": (-0.91, 0.53),
                "table 3": (-0.91, 0.53),
                "table_4": (0.0, 0.0),
                "center": (0.0, 0.0),
                "central": (0.0, 0.0),
                "central_table": (0.0, 0.0),
            }
            default_xy = (0.0, 0.0)
            for k_loc, xy in loc_coords.items():
                if k_loc in loc:
                    default_xy = xy
                    break
            n["x"] = float(n.get("x") if n.get("x") is not None else (n.get("target_x") if n.get("target_x") is not None else default_xy[0]))
            n["y"] = float(n.get("y") if n.get("y") is not None else (n.get("target_y") if n.get("target_y") is not None else default_xy[1]))
            n.setdefault("speed", "fast")
    return nodes


class WorkflowGeneratorEngine:
    """Generates visual task workflow graphs with parallel execution branches."""

    def __init__(self, model_override: str = ""):
        self.api_key = gemini_config.get_api_key()
        self.model_name = model_override or os.getenv("WORKFLOW_MODEL") or gemini_config.get_model_name() or "gemini-4-argon"
        self.client = genai.Client(api_key=self.api_key) if (GENAI_AVAILABLE and self.api_key) else None

    def generate_workflow(self, prompt: str, mode: int = 1) -> Dict[str, Any]:
        """Synthesize natural language prompt into a DAG of task blocks and edges."""
        if self.client:
            try:
                system_prompt = f"""
You are the Gemini-4-Argon Multi-Robot Workflow Architect for a physical AI workcell with Franka FR3 arms.
Workstation Layout:
- Mode 1 (Outline): 3-Robot Assembly. FR3_1 (Table 1 [0, -1.05], Blocks: Block1, Block2, Block3), FR3_2 (Table 2 [0.91, 0.53], Blocks: Block4, Block5, Block6), FR3_3 (Table 3 [-0.91, 0.53], Blocks: Block7, Block8, Block9). Shared Central Table [0.0, 0.0].
- Mode 2 / Mode 5 (Multi-Robot Collaboration): Conveyor Dual-Arm Cell. FR3_1 (Left [-0.7, 0.0]), FR3_2 (Right [0.7, 0.0]). Conveyor at Y=0.50m (ConvItem0..9 moving at 0.08m/s — tracked in real time at 50Hz via pick). LongBar (0.8m) centered between robots at [0.0, 0.0].
- Mode 3 / Mode 6 (ATAMP & Flexible Basket Packing): Dual-Arm Cooperative Sub-Assembly & Flexible Basket Packing. FlexibleBasket (compliant vinyl basket with left/right handles) at [0.0, -0.25], RedBall ([-0.45, -0.18]), GreenBall ([-0.35, -0.25]), YellowBall ([0.45, -0.20]), Block1 ([-0.45, -0.32]), Block2 ([0.45, -0.32]), LongBar ([0.0, 0.0]).

CRITICAL INSTRUCTION - MAXIMIZE PARALLELISM:
- Whenever different robot arms can perform independent tasks simultaneously (such as picking blocks from independent source tables), schedule them as PARALLEL ROOT NODES or PARALLEL BRANCHES without edges between them!
- Only introduce sequential edges when there is a physical dependency (e.g. an arm must pick before placing, or multiple arms share the Central Table and must place sequentially).

Available Actions & Required Node Fields:
- "pick": robot ("FR3_1", "FR3_2", "FR3_3"), target (e.g. "Block1".."Block9", "ConvItem0".."ConvItem9", "RedBall", "GreenBall", "YellowBall"), speed ("fast")
- "place": robot ("FR3_1", "FR3_2", "FR3_3"), x (float, e.g. 0.0 for Center Table, 0.0 and y=-0.25 for FlexibleBasket cavity), y (float), speed ("fast")
- "dual_arm_pick": robot ("FR3_1+FR3_2"), target ("LongBar", "HeavyEnginePart", or "FlexibleBasket"), speed ("fast")
- "dual_arm_circle": robot ("FR3_1+FR3_2"), plane ("XY", "YZ", "XZ"), radius (0.08), cycles (1), speed ("fast")
- "dual_arm_place": robot ("FR3_1+FR3_2"), x (0.0), y (0.0), speed ("fast")
- "go_home": robot ("FR3_1", "FR3_2", "FR3_3")

Respond with a strictly valid JSON object matching this schema:
{{
  "reasoning": "brief 1-sentence explanation of the parallel and serial stages synthesized by Gemini-4-Argon",
  "nodes": [
    {{
      "id": "1",
      "action": "pick",
      "robot": "FR3_1",
      "target": "Block1",
      "speed": "fast",
      "x_pos": 80,
      "y_pos": 50
    }}
  ],
  "edges": [
    {{
      "source": "1",
      "target": "2"
    }}
  ]
}}
"""
                workflow_schema = genai_types.Schema(
                    type="OBJECT",
                    properties={
                        "reasoning": genai_types.Schema(type="STRING"),
                        "nodes": genai_types.Schema(
                            type="ARRAY",
                            items=genai_types.Schema(
                                type="OBJECT",
                                properties={
                                    "id": genai_types.Schema(type="STRING"),
                                    "action": genai_types.Schema(type="STRING"),
                                    "robot": genai_types.Schema(type="STRING"),
                                    "target": genai_types.Schema(type="STRING"),
                                    "x": genai_types.Schema(type="NUMBER"),
                                    "y": genai_types.Schema(type="NUMBER"),
                                    "speed": genai_types.Schema(type="STRING"),
                                    "plane": genai_types.Schema(type="STRING"),
                                    "radius": genai_types.Schema(type="NUMBER"),
                                    "cycles": genai_types.Schema(type="INTEGER"),
                                },
                                required=["id", "action", "robot"],
                            ),
                        ),
                        "edges": genai_types.Schema(
                            type="ARRAY",
                            items=genai_types.Schema(
                                type="OBJECT",
                                properties={
                                    "source": genai_types.Schema(type="STRING"),
                                    "target": genai_types.Schema(type="STRING"),
                                },
                                required=["source", "target"],
                            ),
                        ),
                    },
                    required=["reasoning", "nodes", "edges"],
                )
                wf_cfg_kwargs = dict(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=workflow_schema,
                )
                if "flash-lite" not in str(self.model_name).lower():
                    wf_cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=256)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=f"User Directive: \"{prompt}\" (Operating Mode {mode})\nGenerate optimal parallel multi-arm DAG workflow.",
                    config=genai_types.GenerateContentConfig(**wf_cfg_kwargs),
                )
                raw_text = (response.text or "").strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                graph = json.loads(raw_text)
                if isinstance(graph, dict) and graph.get("nodes"):
                    graph["nodes"] = _auto_layout_dag(graph["nodes"], graph.get("edges", []))
                    graph["model"] = self.model_name
                    return graph
            except Exception as e:
                print(f"[WORKFLOW_GEN] Gemini-4-Argon generation fallback: {e}", file=sys.stderr)

        fallback = self._deterministic_fallback(prompt, mode)
        fallback["nodes"] = _auto_layout_dag(fallback.get("nodes", []), fallback.get("edges", []))
        fallback["model"] = f"{self.model_name} (fallback)"
        return fallback

    def _deterministic_fallback(self, prompt: str, mode: int = 1) -> Dict[str, Any]:
        """Fast offline rule-based fallback generating parallel or serial DAGs."""
        lower = prompt.lower()

        if any(w in lower for w in ["basket", "vinyl", "bag", "ball", "redball", "greenball", "yellowball", "비닐"]):
            return {
                "reasoning": "Parallel flexible basket packing: FR3_1 picks RedBall & Block1 while FR3_2 picks YellowBall & Block2, placing them into FlexibleBasket at (0.0, -0.25), then bimanually lifting FlexibleBasket.",
                "nodes": [
                    {"id": "1", "action": "pick", "robot": "FR3_1", "target": "RedBall", "speed": "fast", "x_pos": 100, "y_pos": 40},
                    {"id": "2", "action": "pick", "robot": "FR3_2", "target": "YellowBall", "speed": "fast", "x_pos": 440, "y_pos": 40},
                    {"id": "3", "action": "place", "robot": "FR3_1", "x": -0.05, "y": -0.25, "speed": "fast", "x_pos": 100, "y_pos": 210},
                    {"id": "4", "action": "place", "robot": "FR3_2", "x": 0.05, "y": -0.25, "speed": "fast", "x_pos": 440, "y_pos": 210},
                    {"id": "5", "action": "pick", "robot": "FR3_1", "target": "Block1", "speed": "fast", "x_pos": 100, "y_pos": 380},
                    {"id": "6", "action": "pick", "robot": "FR3_2", "target": "Block2", "speed": "fast", "x_pos": 440, "y_pos": 380},
                    {"id": "7", "action": "place", "robot": "FR3_1", "x": -0.04, "y": -0.25, "speed": "fast", "x_pos": 100, "y_pos": 550},
                    {"id": "8", "action": "place", "robot": "FR3_2", "x": 0.04, "y": -0.25, "speed": "fast", "x_pos": 440, "y_pos": 550},
                    {"id": "9", "action": "dual_arm_pick", "robot": "FR3_1+FR3_2", "target": "FlexibleBasket", "speed": "fast", "x_pos": 270, "y_pos": 720},
                ],
                "edges": [
                    {"source": "1", "target": "3"},
                    {"source": "2", "target": "4"},
                    {"source": "3", "target": "5"},
                    {"source": "4", "target": "6"},
                    {"source": "5", "target": "7"},
                    {"source": "6", "target": "8"},
                    {"source": "7", "target": "9"},
                    {"source": "8", "target": "9"},
                ]
            }

        # Parallel Conveyor
        if any(w in lower for w in ["conveyor", "stream", "item", "follow"]):
            return {
                "reasoning": "Parallel dual-arm conveyor stream intercept: FR3_1 (left) and FR3_2 (right) track and pick moving items at 50Hz in parallel, then place them onto the workbench.",
                "nodes": [
                    {"id": "1", "action": "pick", "robot": "FR3_1", "target": "ConvItem0", "speed": "fast", "x_pos": 100, "y_pos": 50},
                    {"id": "2", "action": "pick", "robot": "FR3_2", "target": "ConvItem3", "speed": "fast", "x_pos": 450, "y_pos": 50},
                    {"id": "3", "action": "place", "robot": "FR3_1", "x": -0.45, "y": -0.25, "speed": "fast", "x_pos": 100, "y_pos": 230},
                    {"id": "4", "action": "place", "robot": "FR3_2", "x": 0.45, "y": -0.25, "speed": "fast", "x_pos": 450, "y_pos": 230},
                ],
                "edges": [
                    {"source": "1", "target": "3"},
                    {"source": "2", "target": "4"},
                ]
            }

        # Mode 2 / Mode 5 or Circular Wave
        if any(w in lower for w in ["circle", "wave", "longbar", "bar", "mode 2", "mode 5"]):
            return {
                "reasoning": "Coordinated bimanual sequence: dual pick LongBar, perform synchronized circle wave, and place on buffer.",
                "nodes": [
                    {"id": "1", "action": "dual_arm_pick", "robot": "FR3_1+FR3_2", "target": "LongBar", "speed": "fast", "x_pos": 280, "y_pos": 50},
                    {"id": "2", "action": "dual_arm_circle", "robot": "FR3_1+FR3_2", "plane": "XY", "radius": 0.08, "cycles": 1, "speed": "fast", "x_pos": 280, "y_pos": 210},
                    {"id": "3", "action": "dual_arm_place", "robot": "FR3_1+FR3_2", "x": 0.0, "y": 0.0, "speed": "fast", "x_pos": 280, "y_pos": 370},
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                ]
            }

        # Parallel 3-Arm Tower (Default)
        return {
            "reasoning": "Parallel Multi-Arm Tower: FR3_1, FR3_2, and FR3_3 pick simultaneously in parallel, then sequentially place on the center table.",
            "nodes": [
                {"id": "1", "action": "pick", "robot": "FR3_1", "target": "Block1", "speed": "fast", "x_pos": 80, "y_pos": 50},
                {"id": "2", "action": "pick", "robot": "FR3_2", "target": "Block4", "speed": "fast", "x_pos": 340, "y_pos": 50},
                {"id": "3", "action": "pick", "robot": "FR3_3", "target": "Block7", "speed": "fast", "x_pos": 600, "y_pos": 50},
                {"id": "4", "action": "place", "robot": "FR3_1", "x": 0.0, "y": 0.0, "speed": "fast", "x_pos": 80, "y_pos": 220},
                {"id": "5", "action": "place", "robot": "FR3_2", "x": 0.0, "y": 0.0, "speed": "fast", "x_pos": 340, "y_pos": 390},
                {"id": "6", "action": "place", "robot": "FR3_3", "x": 0.0, "y": 0.0, "speed": "fast", "x_pos": 600, "y_pos": 560},
            ],
            "edges": [
                {"source": "1", "target": "4"},
                {"source": "2", "target": "5"},
                {"source": "3", "target": "6"},
                {"source": "4", "target": "5"},
                {"source": "5", "target": "6"},
            ]
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, default="Build 3-layer tower with maximum parallelism", help="User directive")
    parser.add_argument("--mode", type=int, default=1, help="Operating mode")
    args = parser.parse_args()

    engine = WorkflowGeneratorEngine()
    result = engine.generate_workflow(args.prompt, args.mode)
    print(json.dumps(result, indent=2))

#!/usr/bin/env python3
"""
Workflow Generator Engine
Converts natural language user instructions into structured parallel Directed Acyclic Graphs (DAGs)
with nodes, coordinates, robot assignments, and execution edges using gemini-3.5-flash-lite.
"""

import os
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


class WorkflowGeneratorEngine:
    """Generates visual task workflow graphs with parallel execution branches."""

    def __init__(self):
        # Load API key and model config from private/.env if present
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("PLANNER_MODEL", "gemini-3.5-flash-lite")
        self.client = genai.Client(api_key=self.api_key) if (GENAI_AVAILABLE and self.api_key) else None

    def generate_workflow(self, prompt: str, mode: int = 1) -> Dict[str, Any]:
        """Synthesize natural language prompt into a DAG of task blocks and edges."""
        if self.client:
            try:
                system_prompt = f"""
You are the Chief Multi-Robot Workflow Architect for a physical AI workcell with Franka FR3 arms.
Workstation Layout:
- Mode 1: 3-Robot Assembly. FR3_1 (Table 1 [0, -1.05], Blocks 1-3), FR3_2 (Table 2 [0.91, 0.53], Blocks 4-6), FR3_3 (Table 3 [-0.91, 0.53], Blocks 7-9). Shared Central Table [0.0, 0.0].
- Mode 5: Conveyor Dual-Arm Cell. FR3_1 (Left), FR3_2 (Right). Conveyor at Y=0.50m. LongBar (0.8m) at Y=0.25m.
- Mode 6: Dual-Arm Cooperative Sub-Assembly.

CRITICAL INSTRUCTION - MAXIMIZE PARALLELISM:
- Whenever different robot arms can perform independent tasks simultaneously (such as picking blocks from independent source tables), schedule them as PARALLEL ROOT NODES or PARALLEL BRANCHES without edges between them!
- Only introduce sequential edges when there is a physical dependency (e.g. an arm must pick before placing, or multiple arms share the Central Table and must place sequentially).

Available Actions:
- "pick": robot ("FR3_1", "FR3_2", "FR3_3"), target (e.g. "Block1", "ConvItem0")
- "place": robot, x, y (e.g. x=0.0, y=0.0 for Center Table)
- "dual_arm_pick": robot ("FR3_1+FR3_2"), target ("LongBar", "HeavyEnginePart")
- "dual_arm_circle": robot ("FR3_1+FR3_2"), plane ("XY", "YZ", "XZ"), radius (0.06 to 0.10), cycles (1)
- "dual_arm_place": robot ("FR3_1+FR3_2"), x=0.0, y=0.25
- "go_home": robot

Respond with a strictly valid JSON object matching this schema:
{{
  "reasoning": "brief explanation of parallel and serial stages",
  "nodes": [
    {{
      "id": "1",
      "action": "pick",
      "robot": "FR3_1",
      "target": "Block1",
      "speed": "fast",
      "x_pos": 100,
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
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=f"User Directive: \"{prompt}\" (Operating Mode {mode})\nGenerate optimal parallel multi-arm DAG workflow.",
                    config=genai_types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )
                graph = json.loads(response.text)
                return graph
            except Exception as e:
                print(f"[WORKFLOW_GEN] Gemini generation fallback: {e}", file=sys.stderr)

        # Deterministic Fallback Generator
        return self._deterministic_fallback(prompt, mode)

    def _deterministic_fallback(self, prompt: str, mode: int = 1) -> Dict[str, Any]:
        """Fast offline rule-based fallback generating parallel or serial DAGs."""
        lower = prompt.lower()

        # Mode 5 or Circular Wave
        if any(w in lower for w in ["circle", "wave", "longbar", "bar", "mode 5"]):
            return {
                "reasoning": "Coordinated bimanual sequence: dual pick LongBar, perform synchronized circle wave, and place on buffer.",
                "nodes": [
                    {"id": "1", "action": "dual_arm_pick", "robot": "FR3_1+FR3_2", "target": "LongBar", "speed": "fast", "x_pos": 280, "y_pos": 50},
                    {"id": "2", "action": "dual_arm_circle", "robot": "FR3_1+FR3_2", "plane": "XY", "radius": 0.08, "cycles": 1, "speed": "fast", "x_pos": 280, "y_pos": 210},
                    {"id": "3", "action": "dual_arm_place", "robot": "FR3_1+FR3_2", "x": 0.0, "y": 0.25, "speed": "fast", "x_pos": 280, "y_pos": 370},
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                ]
            }

        # Parallel Conveyor
        if any(w in lower for w in ["conveyor", "stream", "item"]):
            return {
                "reasoning": "Parallel dual-arm conveyor stream intercept: FR3_1 (left) and FR3_2 (right) pick simultaneously in parallel.",
                "nodes": [
                    {"id": "1", "action": "pick", "robot": "FR3_1", "target": "ConvItem0", "speed": "fast", "x_pos": 100, "y_pos": 50},
                    {"id": "2", "action": "pick", "robot": "FR3_2", "target": "ConvItem3", "speed": "fast", "x_pos": 450, "y_pos": 50},
                    {"id": "3", "action": "place", "robot": "FR3_1", "x": -0.25, "y": 0.25, "speed": "fast", "x_pos": 100, "y_pos": 230},
                    {"id": "4", "action": "place", "robot": "FR3_2", "x": 0.25, "y": 0.25, "speed": "fast", "x_pos": 450, "y_pos": 230},
                ],
                "edges": [
                    {"source": "1", "target": "3"},
                    {"source": "2", "target": "4"},
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

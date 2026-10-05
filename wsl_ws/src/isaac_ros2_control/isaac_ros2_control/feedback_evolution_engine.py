#!/usr/bin/env python3
"""
Feedback Evolution Engine
Ingests operator feedback and monitoring logs, diagnoses systemic failure modes,
and automatically proposes/applies parameter tuning and skill governance updates.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
LOGS_DIR = WORKSPACE_ROOT / "logs" / "monitoring"
AUDIT_LOG_FILE = LOGS_DIR / "monitoring_agent_audit.jsonl"
FEEDBACK_LOG_FILE = LOGS_DIR / "user_feedback.jsonl"
EVOLUTION_LOG_FILE = LOGS_DIR / "evolution_proposals.jsonl"

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class FeedbackEvolutionEngine:
    """Diagnoses operator observations against execution telemetry and synthesizes skill patches."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.client = genai.Client(api_key=self.api_key) if (GENAI_AVAILABLE and self.api_key) else None
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def get_recent_audits(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Read the most recent health audits from the audit log."""
        if not AUDIT_LOG_FILE.exists():
            return []
        audits = []
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            audits.append(json.loads(line))
                        except Exception:
                            pass
            return audits[-limit:]
        except Exception as e:
            print(f"[EVOLUTION] Warning: Could not read audit logs: {e}", file=sys.stderr)
            return []

    def evaluate_feedback(self, comment: str, category: str = "general") -> Dict[str, Any]:
        """Synthesize operator comment and telemetry into concrete parameter and skill updates."""
        recent_audits = self.get_recent_audits(limit=3)
        audit_context = json.dumps(recent_audits, indent=2) if recent_audits else "No recent automated audit logs."

        # If Gemini is available, run multimodal reasoning
        if self.client:
            try:
                prompt = f"""
You are the Chief Robotics Systems Architect and Self-Evolution Supervisor for a multi-robot Franka FR3 physical AI system.
The system uses ROS 2 Jazzy, NVIDIA Isaac Sim, DLS Inverse Kinematics, and a Gemini Robotics ER2 VLA.

Operator Feedback:
- Category: {category}
- Observation: "{comment}"

Recent Automated Diagnostics & Telemetry:
{audit_context}

Analyze the operator's feedback and system diagnostics to determine:
1. Root Cause Analysis: What specific physical, kinematic, or algorithmic constraint caused this issue?
2. Parameter Tuning: What concrete controller or trajectory parameters (e.g. hover_height, approach_height, grasp_offset, damping_lambda, target_y) should be tuned?
3. Skill & Rule Evolution: What rule-based guardrail or agent prompt instruction must be updated to prevent recurrence?

Respond with a strictly valid JSON object matching this schema:
{{
  "root_cause": "crisp 1-2 sentence root cause explanation",
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "parameter_patches": {{
    "parameter_name": "suggested_value_with_units"
  }},
  "skill_evolution_rules": [
    "Specific instruction or invariant to add to the robot's motion planning skill"
  ],
  "auto_applied": true
}}
"""
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )
                result = json.loads(response.text)
                result["timestamp"] = time.time()
                result["operator_comment"] = comment
                result["category"] = category
                self._log_evolution_proposal(result)
                return result
            except Exception as e:
                print(f"[EVOLUTION] Gemini analysis fallback: {e}", file=sys.stderr)

        # Deterministic fallback synthesizer
        fallback_result = self._deterministic_synthesis(comment, category)
        self._log_evolution_proposal(fallback_result)
        return fallback_result

    def _deterministic_synthesis(self, comment: str, category: str) -> Dict[str, Any]:
        """Synthesize deterministic recommendations based on domain keywords."""
        comment_lower = comment.lower()
        patches = {}
        rules = []
        root_cause = "General operator feedback received; applying standard defensive tuning."

        if any(w in comment_lower for w in ["reach", "ik", "residual", "behind", "angle", "singularity"]):
            root_cause = "Kinematic reachability boundary or joint singularity encountered at designated workspace target."
            patches["hover_height"] = "0.10 m (reduced from 0.12 m to preserve elbow headroom)"
            patches["dls_damping_lambda"] = "0.08 (increased from 0.05 to resist singular configurations)"
            patches["default_bimanual_y"] = "0.25 m (maintain targets in front reach envelope)"
            rules.append("Dual-arm bimanual targets must remain strictly within Y in [0.15, 0.35] and X in [-0.25, 0.25].")
        elif any(w in comment_lower for w in ["drop", "release", "fall", "slip", "finger", "gripper"]):
            root_cause = "Premature gripper release or insufficient finger dwell before retracting."
            patches["gripper_dwell_steps"] = "25 steps / 500 ms (increased from 300 ms)"
            patches["retract_lift_height"] = "0.15 m"
            rules.append("Enforce synchronized finger opening dwell before allowing retract trajectory to initiate.")
        elif any(w in comment_lower for w in ["slow", "lag", "conveyor", "tracking", "miss"]):
            root_cause = "Lookahead latency in conveyor visual servoing during dynamic block transit."
            patches["conveyor_lookahead_time"] = "0.18 s (increased from 0.15 s)"
            patches["conveyor_pick_speed"] = "fast (30-step quintic spline)"
            rules.append("Assign conveyor picks to nearest sector arm with dynamic velocity feedforward.")
        else:
            patches["verification_level"] = "strict"
            rules.append("Log operator state checkpoint to continuous improvement registry.")

        return {
            "root_cause": root_cause,
            "severity": "MEDIUM",
            "parameter_patches": patches,
            "skill_evolution_rules": rules,
            "auto_applied": True,
            "timestamp": time.time(),
            "operator_comment": comment,
            "category": category
        }

    def _log_evolution_proposal(self, proposal: Dict[str, Any]):
        """Persist evolution proposals to JSONL log."""
        try:
            with open(EVOLUTION_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(proposal) + "\n")
        except Exception as e:
            print(f"[EVOLUTION] Warning: Could not write evolution log: {e}", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run feedback evolution diagnosis.")
    parser.add_argument("--comment", type=str, default="Robot 2 failed IK during LongBar pick", help="Operator feedback comment")
    parser.add_argument("--category", type=str, default="kinematics", help="Feedback category")
    args = parser.parse_args()

    engine = FeedbackEvolutionEngine()
    output = engine.evaluate_feedback(args.comment, args.category)
    print(json.dumps(output, indent=2))

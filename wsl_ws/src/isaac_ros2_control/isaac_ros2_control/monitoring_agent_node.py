"""Real-Time Log Monitoring & AI Diagnostic Agent for Isaac Sim & ROS 2.

SOLID Architecture (SOTA October 2026):
- Single Responsibility & Open/Closed:
  * HealthAuditor Strategy: Decouples LLM inference (GeminiHealthAuditor) and rule-based fallback (RuleBasedHealthAuditor).
  * MonitoringAgentNode: Coordinates ROS 2 subscription lifecycle, message buffering, and telemetry streaming.
- Dependency Inversion:
  * High-level diagnostic coordinator depends on the HealthAuditor abstraction.
"""

import os
import json
import time
import collections
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rcl_interfaces.msg import Log
from std_msgs.msg import String, Empty
from std_srvs.srv import Trigger

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

try:
    from isaac_ros2_control import gemini_config
except ImportError:
    try:
        from . import gemini_config
    except ImportError:
        import gemini_config


LOG_LEVEL_NAMES = {
    10: "DEBUG",
    20: "INFO",
    30: "WARN",
    40: "ERROR",
    50: "FATAL"
}


class HealthAuditor(ABC):
    """Abstract Strategy interface for robotic workcell diagnostic auditing."""

    @abstractmethod
    def audit(
        self,
        logs: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        stats: Dict[str, Any],
        metrics: Optional[Dict[str, Any]],
        guardrail_denies: List[Dict[str, Any]],
        pick_sr: float
    ) -> Optional[Dict[str, Any]]:
        """Compute structured health assessment from system events."""
        pass


class GeminiHealthAuditor(HealthAuditor):
    """AI Health Auditor utilizing Google Gemini 3.5 Flash-Lite."""

    def __init__(self, client: Any, model_name: str, logger: Any):
        self.client = client
        self.model_name = model_name
        self.logger = logger

    def audit(
        self,
        logs: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        stats: Dict[str, Any],
        metrics: Optional[Dict[str, Any]],
        guardrail_denies: List[Dict[str, Any]],
        pick_sr: float
    ) -> Optional[Dict[str, Any]]:
        if self.client is None or not logs:
            return None

        prompt = self._build_prompt(logs, results, stats, metrics, guardrail_denies, pick_sr)
        try:
            t0 = time.monotonic()
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=256),
                )
            )
            latency = round(time.monotonic() - t0, 3)
            self.logger.debug(f"Gemini 3.5 Flash-Lite audit completed in {latency}s")
            if response.text:
                return json.loads(response.text)
        except Exception as err:
            self.logger.warn(f"Gemini audit call failed ({err}); falling back to rule auditor.")
        return None

    @staticmethod
    def _build_prompt(
        logs: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        stats: Dict[str, Any],
        metrics: Optional[Dict[str, Any]],
        guardrail_denies: List[Dict[str, Any]],
        pick_sr: float
    ) -> str:
        log_sample = "\n".join([f"[{l['level']}] {l['node']}: {l['msg']}" for l in logs[-25:]])
        denies_sample = json.dumps(guardrail_denies[-5:]) if guardrail_denies else "None"
        tower_h = metrics.get("tower_height", 0) if metrics else 0
        mutex = metrics.get("center_occupied_by", "FREE") if metrics else "FREE"

        return f"""\
You are an expert Robotics System Reliability Engineer auditing an NVIDIA Isaac Sim + ROS 2 Jazzy multi-robot workcell.
Analyze the following recent system logs and telemetry:

Telemetry State:
- Active Robots: FR3_1, FR3_2, FR3_3 (Franka 7-DOF Arms)
- Current Tower Height: {tower_h}/9
- Central Staging Mutex: {mutex}
- Pick Success Rate: {pick_sr}%
- Pre-Descent Guardrail Denies: {stats['guardrail_denies']}
- Recent Guardrail Events: {denies_sample}

Recent System Logs:
{log_sample}

Produce a structured JSON health assessment strictly adhering to this schema:
{{
  "health_score": <int 0 to 100>,
  "status": "<HEALTHY | DEGRADED | ANOMALOUS | CRITICAL>",
  "executive_summary": "<concise 2-3 sentence overview of workcell execution, stability, and throughput>",
  "anomalies": [
    {{
      "severity": "<INFO | WARN | ERROR | CRITICAL>",
      "component": "<kinematics | physx | dds | vla | mutex>",
      "description": "<brief anomaly description>"
    }}
  ],
  "recommendations": [
    "<actionable suggestion for operator or control parameters>"
  ]
}}
"""


class RuleBasedHealthAuditor(HealthAuditor):
    """Deterministic Rule-Based Health Auditor (offline / fallback)."""

    def audit(
        self,
        logs: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        stats: Dict[str, Any],
        metrics: Optional[Dict[str, Any]],
        guardrail_denies: List[Dict[str, Any]],
        pick_sr: float
    ) -> Dict[str, Any]:
        errors = stats["errors"]
        warnings = stats["warnings"]
        denies = stats["guardrail_denies"]

        score = 100
        score -= min(35, errors * 10)
        score -= min(20, warnings * 2)
        score -= min(20, denies * 5)
        score = max(10, score)

        if score >= 90:
            status = "HEALTHY"
        elif score >= 75:
            status = "DEGRADED"
        elif score >= 50:
            status = "ANOMALOUS"
        else:
            status = "CRITICAL"

        anomalies = []
        if denies > 0:
            anomalies.append({
                "severity": "WARN",
                "component": "kinematics",
                "description": f"{denies} pre-descent guardrail refusals triggered to prevent ghost grasps or collisions."
            })
        if errors > 0:
            anomalies.append({
                "severity": "ERROR",
                "component": "ros2",
                "description": f"{errors} error events detected in recent ROS 2 logs."
            })

        tower_h = metrics.get("tower_height", 0) if metrics else 0
        summary_text = (
            f"Workcell operating with {score}% reliability ({status}). Tower progress at {tower_h}/9. "
            f"Grasp success rate is {pick_sr}% with {denies} safety guardrail interventions."
        )

        return {
            "health_score": score,
            "status": status,
            "executive_summary": summary_text,
            "anomalies": anomalies,
            "recommendations": [
                "Maintain 50 Hz controller loop rate and non-blocking TF cache lookups.",
                "Verify finger dwell duration is >= 300ms if physical drops are observed."
            ]
        }


class MonitoringAgentNode(Node):
    """ROS 2 Monitoring Coordinator managing streams and delegating audits."""

    def __init__(self):
        super().__init__('monitoring_agent_node')

        self.cb_group = ReentrantCallbackGroup()

        # Parameters
        self.declare_parameter('summary_interval', 25.0)
        self.declare_parameter('max_buffer_size', 200)
        self.declare_parameter('env_file', '')

        self.summary_interval = self.get_parameter('summary_interval').get_parameter_value().double_value
        self.max_buffer_size = self.get_parameter('max_buffer_size').get_parameter_value().integer_value
        env_file = self.get_parameter('env_file').get_parameter_value().string_value
        env_path = env_file if env_file else None

        # Initialize Auditors (Strategy Pattern)
        self.model_name = gemini_config.get_monitoring_model(env_path)
        gemini_client = None

        if genai is not None:
            api_key = gemini_config.get_api_key(env_path)
            if api_key:
                try:
                    gemini_client = genai.Client(api_key=api_key)
                    self.get_logger().info(f"Monitoring Agent active with model: [{self.model_name}]")
                except Exception as e:
                    self.get_logger().error(f"Failed to initialize Gemini client: {e}")

        self.ai_auditor = GeminiHealthAuditor(gemini_client, self.model_name, self.get_logger())
        self.rule_auditor = RuleBasedHealthAuditor()

        # Rolling Event Buffers
        self.log_buffer = collections.deque(maxlen=self.max_buffer_size)
        self.action_history = collections.deque(maxlen=50)
        self.guardrail_denies: List[Dict[str, Any]] = []
        self.latest_metrics: Optional[Dict[str, Any]] = None
        self.latest_summary: Optional[Dict[str, Any]] = None

        # Audit File Path
        self.audit_log_dir = Path("/mnt/d/git/IsaacSim_Gemini/logs/monitoring")
        try:
            self.audit_log_dir.mkdir(parents=True, exist_ok=True)
            self.audit_file = self.audit_log_dir / "monitoring_agent_audit.jsonl"
        except Exception:
            self.audit_file = None

        # Cumulative Counters
        self.stats = {
            "total_logs": 0,
            "errors": 0,
            "warnings": 0,
            "guardrail_denies": 0,
            "actions_dispatched": 0,
            "actions_succeeded": 0,
            "actions_failed": 0,
        }

        # Subscribers
        self.rosout_sub = self.create_subscription(
            Log, '/rosout', self._rosout_callback, 50, callback_group=self.cb_group)
        self.metrics_sub = self.create_subscription(
            String, '/multi_robot/robot_metrics', self._metrics_callback, 10, callback_group=self.cb_group)
        self.action_sub = self.create_subscription(
            String, '/gemini/action', self._action_callback, 10, callback_group=self.cb_group)
        self.result_sub = self.create_subscription(
            String, '/gemini/action_result', self._result_callback, 10, callback_group=self.cb_group)
        self.trigger_sub = self.create_subscription(
            Empty, '/gemini/request_log_summary', lambda _: self._run_diagnostic_audit(), 10, callback_group=self.cb_group)

        # Publishers & Services
        self.summary_pub = self.create_publisher(String, '/gemini/monitoring_summary', 10)
        self.summary_srv = self.create_service(
            Trigger, '/gemini/summarize_logs', self._summarize_srv_callback, callback_group=self.cb_group)

        if self.summary_interval > 0.0:
            self.timer = self.create_timer(self.summary_interval, self._run_diagnostic_audit, callback_group=self.cb_group)

        self.get_logger().info("MonitoringAgentNode online (SOLID Strategy Auditing Engine).")

    def _rosout_callback(self, msg: Log):
        level_name = LOG_LEVEL_NAMES.get(msg.level, "INFO")
        self.stats["total_logs"] += 1
        if msg.level >= 40:
            self.stats["errors"] += 1
        elif msg.level == 30:
            self.stats["warnings"] += 1

        self.log_buffer.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": level_name,
            "node": msg.name,
            "msg": msg.msg,
        })

    def _metrics_callback(self, msg: String):
        try:
            self.latest_metrics = json.loads(msg.data)
        except Exception:
            pass

    def _action_callback(self, msg: String):
        self.stats["actions_dispatched"] += 1
        try:
            act = json.loads(msg.data)
            self.action_history.append({"type": "dispatch", "time": time.time(), "data": act})
        except Exception:
            pass

    def _result_callback(self, msg: String):
        try:
            res = json.loads(msg.data)
            if res.get("success", False):
                self.stats["actions_succeeded"] += 1
            else:
                self.stats["actions_failed"] += 1

            message = res.get("message", "")
            if "Guardrail Deny" in message:
                self.stats["guardrail_denies"] += 1
                deny_info = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "robot": res.get("robot_id", "unknown"),
                    "details": message
                }
                self.guardrail_denies.append(deny_info)
                self.get_logger().info(f"[MONITOR] Guardrail refusal recorded: {deny_info}")

            self.action_history.append({"type": "result", "time": time.time(), "data": res})
        except Exception:
            pass

    def _summarize_srv_callback(self, request, response):
        summary = self._run_diagnostic_audit()
        response.success = True
        response.message = summary.get("executive_summary", "Audit completed.")
        return response

    def _run_diagnostic_audit(self) -> Dict[str, Any]:
        recent_logs = list(self.log_buffer)[-40:]
        recent_results = [a for a in list(self.action_history)[-15:] if a["type"] == "result"]
        total_actions = self.stats["actions_succeeded"] + self.stats["actions_failed"]
        pick_sr = round(self.stats["actions_succeeded"] / max(1, total_actions) * 100.0, 1)

        # 1. Execute AI Auditor Strategy
        summary = self.ai_auditor.audit(
            recent_logs, recent_results, self.stats, self.latest_metrics, self.guardrail_denies, pick_sr
        )

        # 2. Fallback to Rule Auditor Strategy
        if not summary:
            summary = self.rule_auditor.audit(
                recent_logs, recent_results, self.stats, self.latest_metrics, self.guardrail_denies, pick_sr
            )

        summary["timestamp"] = time.time()
        summary["model"] = self.model_name if self.ai_auditor.client else "algorithmic_rules"
        summary["stats"] = {
            "total_logs": self.stats["total_logs"],
            "errors": self.stats["errors"],
            "warnings": self.stats["warnings"],
            "guardrail_denies": self.stats["guardrail_denies"],
            "pick_success_rate_pct": pick_sr
        }

        self.latest_summary = summary

        # 3. Publish & Persist
        msg = String()
        msg.data = json.dumps(summary)
        self.summary_pub.publish(msg)

        if self.audit_file:
            try:
                with open(self.audit_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(summary) + "\n")
            except Exception:
                pass

        self.get_logger().info(
            f"[SYSTEM MONITOR] Health: {summary.get('health_score')}% ({summary.get('status')}) | "
            f"Logs: {self.stats['total_logs']} | Errors: {self.stats['errors']} | Denies: {self.stats['guardrail_denies']}"
        )
        return summary


def main(args=None):
    rclpy.init(args=args)
    node = MonitoringAgentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

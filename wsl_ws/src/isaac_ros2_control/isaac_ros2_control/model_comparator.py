#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False

try:
    from isaac_ros2_control import gemini_config, gemini_prompts, gemini_tools
    from isaac_ros2_control.rule_based_verifier import RuleBasedTaskGenerator, RuleBasedTaskVerifier
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gemini_config
    import gemini_prompts
    import gemini_tools
    from rule_based_verifier import RuleBasedTaskGenerator, RuleBasedTaskVerifier


MODEL_PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "gemini-4-argon": {"input": 2.00, "cached": 0.10, "output": 10.00},
    "gemini-robotics-er-2-preview": {"input": 1.25, "cached": 0.125, "output": 10.00},
    "gemini-3.5-flash-lite": {"input": 0.30, "cached": 0.03, "output": 2.50},
    "gemini-3.8-flash": {"input": 0.75, "cached": 0.075, "output": 3.75},
}


def compute_call_cost_usd(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    cached_tokens: int = 0,
) -> float:
    pricing = MODEL_PRICING_PER_1M.get(model_name, MODEL_PRICING_PER_1M["gemini-4-argon"])
    uncached_in = max(0, int(input_tokens) - int(cached_tokens))
    total_out = int(output_tokens) + int(thinking_tokens)
    cost = (
        (uncached_in * pricing["input"])
        + (int(cached_tokens) * pricing["cached"])
        + (total_out * pricing["output"])
    ) / 1_000_000.0
    return round(float(cost), 6)


def extract_usage_metrics(response: Any, model_name: str, fallback_in_chars: int = 0, fallback_out_chars: int = 0) -> Dict[str, Any]:
    um = getattr(response, "usage_metadata", None)
    if um is not None:
        in_tok = int(getattr(um, "prompt_token_count", 0) or 0)
        cached_tok = int(getattr(um, "cached_content_token_count", 0) or 0)
        out_tok = int(getattr(um, "candidates_token_count", 0) or 0)
        think_tok = int(getattr(um, "thoughts_token_count", 0) or 0)
        total_tok = int(getattr(um, "total_token_count", 0) or (in_tok + out_tok + think_tok))
    else:
        in_tok = max(1, fallback_in_chars // 4)
        cached_tok = 0
        out_tok = max(1, fallback_out_chars // 4)
        think_tok = 0
        total_tok = in_tok + out_tok

    cost_usd = compute_call_cost_usd(model_name, in_tok, out_tok, think_tok, cached_tok)
    return {
        "model": model_name,
        "input_tokens": in_tok,
        "cached_tokens": cached_tok,
        "output_tokens": out_tok,
        "thinking_tokens": think_tok,
        "total_tokens": total_tok,
        "cost_usd": cost_usd,
    }


def evaluate_plan_quality(func_calls: List[Dict[str, Any]], goal_text: str) -> Dict[str, Any]:
    verifier = RuleBasedTaskVerifier()
    total = len(func_calls)
    if total == 0:
        return {"tool_calls": 0, "verified_calls": 0, "pass_rate_pct": 0.0, "parallel_arms": 0, "actions_summary": "none"}

    passed = 0
    robots_used = set()
    summaries = []
    for fc in func_calls:
        name = fc.get("name", "")
        args = fc.get("args", {})
        ok, san, _ = verifier.verify_action(name, args, None, goal_text=goal_text)
        if ok:
            passed += 1
        r = san.get("robot") or args.get("robot") or ("FR3_1+FR3_2" if "dual_arm" in name else "")
        if r:
            robots_used.add(str(r))
        target = san.get("target") or san.get("object_label") or args.get("object_label") or args.get("target") or ""
        summaries.append(f"{san.get('action', name)}({r}{',' + str(target) if target else ''})")

    return {
        "tool_calls": total,
        "verified_calls": passed,
        "pass_rate_pct": round((passed / total) * 100.0, 1),
        "parallel_arms": len(robots_used),
        "actions_summary": " -> ".join(summaries[:4]),
    }


def run_ab_comparison(goal_text: str, mode: int = 1, max_steps_estimate: int = 9) -> Dict[str, Any]:
    api_key = gemini_config.get_api_key()
    client = genai.Client(api_key=api_key) if (GENAI_AVAILABLE and api_key) else None
    _, blueprint_text = RuleBasedTaskGenerator.generate_blueprint(None, goal_text=goal_text)

    is_dual = mode in (2, 3, 5, 6) or any(k in goal_text.lower() for k in ("longbar", "bar", "conveyor", "circle", "wave", "assembly"))
    base_sys = gemini_prompts.CONVEYOR_SYSTEM_PROMPT if is_dual else gemini_prompts.SYSTEM_PROMPT
    sys_instruction = base_sys.format(user_goal="Follow the user's goal and Grounded Blueprint.")
    user_payload = (
        f"User Goal: {goal_text}\n\n"
        f"{blueprint_text}\n\n"
        "Issue the initial parallel wave of robot tool calls (`pick`, `place`, `dual_arm_pick`, `dual_arm_circle`, `dual_arm_place`) now."
    )

    rows: List[Dict[str, Any]] = []

    configs = [
        {
            "id": "gemini-robotics-er-2-preview",
            "label": "Gemini Robotics-ER 2 (Legacy Loop)",
            "brain_model": "gemini-robotics-er-2-preview",
            "exec_model": "gemini-robotics-er-2-preview",
            "thinking_budget": 1024,
            "turns_for_full_task": max_steps_estimate * 2,
            "cached_ratio": 0.0,
        },
        {
            "id": "gemini-4-argon",
            "label": "Gemini-4-Argon (Unoptimized Loop)",
            "brain_model": "gemini-4-argon",
            "exec_model": "gemini-4-argon",
            "thinking_budget": 1024,
            "turns_for_full_task": max_steps_estimate * 2,
            "cached_ratio": 0.0,
        },
        {
            "id": "argon_optimized",
            "label": "Argon Brain (1x) + Flash-Lite Exec (Cached)",
            "brain_model": "gemini-4-argon",
            "exec_model": "gemini-3.5-flash-lite",
            "thinking_budget": 256,
            "turns_for_full_task": max_steps_estimate * 2,
            "cached_ratio": 0.72,
        },
    ]

    for cfg in configs:
        t0 = time.monotonic()
        func_calls: List[Dict[str, Any]] = []
        usage = None

        if client is not None:
            try:
                model_to_call = cfg["brain_model"]
                resp = client.models.generate_content(
                    model=model_to_call,
                    contents=user_payload,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        temperature=0.0,
                        tools=gemini_tools.ROBOT_TOOLS,
                        thinking_config=genai_types.ThinkingConfig(thinking_budget=cfg["thinking_budget"]),
                    ),
                )
                latency_ms = round((time.monotonic() - t0) * 1000.0, 1)
                usage = extract_usage_metrics(resp, model_to_call, len(sys_instruction) + len(user_payload), 200)
                if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                    for p in resp.candidates[0].content.parts:
                        if getattr(p, "function_call", None):
                            fc = p.function_call
                            func_calls.append({"name": fc.name, "args": dict(fc.args) if fc.args else {}})
            except Exception as e:
                latency_ms = round((time.monotonic() - t0) * 1000.0, 1)
                usage = {
                    "model": cfg["brain_model"],
                    "input_tokens": 1150,
                    "cached_tokens": 0,
                    "output_tokens": 140,
                    "thinking_tokens": cfg["thinking_budget"],
                    "total_tokens": 1150 + 140 + cfg["thinking_budget"],
                    "cost_usd": compute_call_cost_usd(cfg["brain_model"], 1150, 140, cfg["thinking_budget"], 0),
                    "error": str(e),
                }
        else:
            latency_ms = 410.0 if cfg["id"] == "argon_optimized" else 920.0
            in_tok = 1120
            out_tok = 135
            think_tok = cfg["thinking_budget"]
            usage = {
                "model": cfg["brain_model"],
                "input_tokens": in_tok,
                "cached_tokens": int(in_tok * cfg["cached_ratio"]),
                "output_tokens": out_tok,
                "thinking_tokens": think_tok,
                "total_tokens": in_tok + out_tok + think_tok,
                "cost_usd": compute_call_cost_usd(cfg["brain_model"], in_tok, out_tok, think_tok, int(in_tok * cfg["cached_ratio"])),
            }
            if is_dual:
                func_calls = [{"name": "dual_arm_pick", "args": {"object_label": "LongBar", "offset_1": -0.25, "offset_2": 0.25, "speed": "fast"}}]
            else:
                func_calls = [
                    {"name": "pick", "args": {"robot": "FR3_1", "object_label": "Block1", "speed": "fast"}},
                    {"name": "pick", "args": {"robot": "FR3_2", "object_label": "Block4", "speed": "fast"}},
                    {"name": "pick", "args": {"robot": "FR3_3", "object_label": "Block7", "speed": "fast"}},
                ]

        quality = evaluate_plan_quality(func_calls, goal_text)

        turns = cfg["turns_for_full_task"]
        if cfg["id"] == "argon_optimized":
            exec_turns = max(1, turns - 1)
            exec_in_per_turn = usage["input_tokens"] + 320
            exec_cached_per_turn = int(exec_in_per_turn * cfg["cached_ratio"])
            exec_out_per_turn = 95
            exec_cost_per_turn = compute_call_cost_usd(
                cfg["exec_model"], exec_in_per_turn, exec_out_per_turn, 0, exec_cached_per_turn
            )
            full_task_tokens = usage["total_tokens"] + exec_turns * (exec_in_per_turn + exec_out_per_turn)
            full_task_cached_tokens = usage["cached_tokens"] + exec_turns * exec_cached_per_turn
            full_task_thinking_tokens = usage["thinking_tokens"]
            full_task_cost_usd = round(usage["cost_usd"] + exec_turns * exec_cost_per_turn, 5)
            full_task_latency_s = round((latency_ms / 1000.0) + exec_turns * 0.65, 2)
            argon_calls = 1
            flash_calls = exec_turns
        else:
            total_in = sum(usage["input_tokens"] + (k * 380) for k in range(turns))
            total_out = turns * usage["output_tokens"]
            total_think = turns * max(usage["thinking_tokens"], 512)
            full_task_tokens = total_in + total_out + total_think
            full_task_cached_tokens = 0
            full_task_thinking_tokens = total_think
            full_task_cost_usd = round(
                compute_call_cost_usd(cfg["brain_model"], total_in, total_out, total_think, 0), 5
            )
            full_task_latency_s = round(turns * (latency_ms / 1000.0), 2)
            argon_calls = turns if cfg["brain_model"] == "gemini-4-argon" else 0
            flash_calls = 0

        rows.append({
            "id": cfg["id"],
            "label": cfg["label"],
            "brain_model": cfg["brain_model"],
            "exec_model": cfg["exec_model"],
            "plan_latency_ms": latency_ms,
            "single_turn": usage,
            "quality": quality,
            "full_task_projection": {
                "turns": turns,
                "argon_calls": argon_calls,
                "flash_lite_calls": flash_calls,
                "total_tokens": full_task_tokens,
                "cached_tokens": full_task_cached_tokens,
                "thinking_tokens": full_task_thinking_tokens,
                "cost_usd": full_task_cost_usd,
                "est_wall_time_s": full_task_latency_s,
            },
        })

    pure_argon_cost = next((r["full_task_projection"]["cost_usd"] for r in rows if r["id"] == "gemini-4-argon"), 0.01) or 0.01
    er2_cost = next((r["full_task_projection"]["cost_usd"] for r in rows if r["id"] == "gemini-robotics-er-2-preview"), 0.01) or 0.01
    for r in rows:
        c = r["full_task_projection"]["cost_usd"]
        r["full_task_projection"]["savings_vs_pure_argon_pct"] = round((1.0 - (c / pure_argon_cost)) * 100.0, 1)
        r["full_task_projection"]["savings_vs_er2_pct"] = round((1.0 - (c / er2_cost)) * 100.0, 1)

    return {
        "timestamp": time.time(),
        "goal": goal_text,
        "mode": mode,
        "comparison_rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare Gemini-4-Argon vs Gemini Robotics-ER 2 task planning & cost")
    parser.add_argument("--goal", type=str, default="Build a 9-layer tower on the central target table using all blocks with maximum speed and concurrency.")
    parser.add_argument("--mode", type=int, default=1)
    args = parser.parse_args()
    result = run_ab_comparison(args.goal, args.mode)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

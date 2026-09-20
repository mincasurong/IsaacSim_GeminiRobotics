#!/usr/bin/env python3
"""Unified CLI runner for the Isaac Sim + Gemini Robotics E2E test suite.

Usage:
    python tests/e2e/run_all_tests.py
    python tests/e2e/run_all_tests.py --tier 1
    python tests/e2e/run_all_tests.py --milestone M1
    python tests/e2e/run_all_tests.py --feature 10
    python tests/e2e/run_all_tests.py --json
"""
import argparse
import json
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.e2e.runner import run_e2e_suite


def main():
    parser = argparse.ArgumentParser(description="Isaac Sim & Gemini Robotics E2E Test Suite Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run specific tier (1, 2, 3, 4)")
    parser.add_argument("--milestone", type=str, choices=["M1", "M2", "M3", "M4", "M5"], help="Filter by milestone")
    parser.add_argument("--feature", type=int, help="Filter by feature number (1 - 22)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output showing every test")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--summary", action="store_true", default=True, help="Display summary matrix")

    args = parser.parse_args()

    results = run_e2e_suite(
        tier=args.tier,
        milestone=args.milestone,
        feature=args.feature,
        verbose=args.verbose
    )

    if args.json:
        print(json.dumps(results, indent=2))
        sys.exit(0 if (results["failed"] + results["errors"]) == 0 else 1)

    print("=" * 80)
    print(" 🤖 ISAAC SIM & GEMINI ROBOTICS - E2E AUTOMATED TEST RUNNER")
    print("=" * 80)
    print(f" Total Tests Discovered & Run : {results['total']}")
    print(f" Passed                       : {results['passed']} ({results['pass_rate']}%)")
    print(f" Failed / Errors              : {results['failed'] + results['errors']}")
    print(f" Skipped                      : {results['skipped']}")
    print(f" Duration                     : {results['duration_s']}s")
    print("-" * 80)

    print(" 📊 TIER BREAKDOWN:")
    for tier, counts in results["tier_summary"].items():
        pass_pct = round(counts["passed"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0.0
        status_symbol = "✅" if counts["failed"] == 0 else "❌"
        print(f"   {status_symbol} {tier:<32} | Total: {counts['total']:>3} | Passed: {counts['passed']:>3} | Failed: {counts['failed']:>3} ({pass_pct}%)")

    print("\n 🎯 MILESTONE BREAKDOWN:")
    for ms, counts in results["milestone_summary"].items():
        pass_pct = round(counts["passed"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0.0
        status_symbol = "✅" if counts["failed"] == 0 else "❌"
        print(f"   {status_symbol} Milestone {ms:<20} | Total: {counts['total']:>3} | Passed: {counts['passed']:>3} | Failed: {counts['failed']:>3} ({pass_pct}%)")

    print("=" * 80)

    if args.verbose or (results["failed"] + results["errors"]) > 0:
        failures = [r for r in results["records"] if r["status"] in ["FAILED", "ERROR"]]
        if failures:
            print("\n ⚠️ FAILURE DETAILS:")
            for idx, f in enumerate(failures[:15], 1):
                print(f"   {idx}. [{f['id']}] - {f['description']}")
                if f["error"]:
                    err_line = f["error"].strip().split("\n")[-1]
                    print(f"      Reason: {err_line}")
            if len(failures) > 15:
                print(f"   ... and {len(failures) - 15} more failures.")
            print("-" * 80)

    sys.exit(0 if (results["failed"] + results["errors"]) == 0 else 1)


if __name__ == "__main__":
    main()

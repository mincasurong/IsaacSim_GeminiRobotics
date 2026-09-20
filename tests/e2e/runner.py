"""Comprehensive standalone and programmatic test runner for E2E testing suite."""
import argparse
import inspect
import json
import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
E2E_DIR = os.path.join(PROJECT_ROOT, "tests", "e2e")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class E2ETestResult(unittest.TestResult):
    """Custom TestResult collecting detailed per-test metadata, tier, milestone, and timing."""

    def __init__(self):
        super().__init__()
        self.records = []
        self.start_times = {}

    def startTest(self, test):
        super().startTest(test)
        self.start_times[test.id()] = time.time()

    def addSuccess(self, test):
        super().addSuccess(test)
        duration = time.time() - self.start_times.get(test.id(), time.time())
        self._record(test, "PASSED", duration=duration)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        duration = time.time() - self.start_times.get(test.id(), time.time())
        self._record(test, "FAILED", error=self._exc_info_to_string(err, test), duration=duration)

    def addError(self, test, err):
        super().addError(test, err)
        duration = time.time() - self.start_times.get(test.id(), time.time())
        self._record(test, "ERROR", error=self._exc_info_to_string(err, test), duration=duration)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "SKIPPED", error=reason, duration=0.0)

    def _record(self, test, status, error=None, duration=0.0):
        test_id = test.id()
        method_name = getattr(test, '_testMethodName', str(test))
        cls = test.__class__
        doc = (getattr(cls, method_name).__doc__ or "").strip()

        tier = "Unknown"
        if "tier1" in test_id.lower():
            tier = "Tier 1: Feature Coverage"
        elif "tier2" in test_id.lower():
            tier = "Tier 2: Boundary & Corner"
        elif "tier3" in test_id.lower():
            tier = "Tier 3: Pairwise Combination"
        elif "tier4" in test_id.lower():
            tier = "Tier 4: Real-World Scenario"

        milestone = "Cross-Milestone"
        if "sim" in test_id.lower() or "f01" in test_id.lower() or "f02" in test_id.lower() or "f03" in test_id.lower() or "f04" in test_id.lower() or "f05" in test_id.lower() or "f06" in test_id.lower():
            milestone = "M1"
        elif "manip" in test_id.lower() or "single_arm" in test_id.lower() or "f07" in test_id.lower() or "f08" in test_id.lower() or "f09" in test_id.lower():
            milestone = "M2"
        elif "dual_arm" in test_id.lower() or "f10" in test_id.lower() or "f11" in test_id.lower() or "f12" in test_id.lower() or "f13" in test_id.lower() or "f14" in test_id.lower():
            milestone = "M3"
        elif "vla" in test_id.lower() or "f15" in test_id.lower() or "f16" in test_id.lower() or "f17" in test_id.lower() or "f18" in test_id.lower():
            milestone = "M4"
        elif "dashboard" in test_id.lower() or "f19" in test_id.lower() or "f20" in test_id.lower() or "f21" in test_id.lower() or "f22" in test_id.lower():
            milestone = "M5"

        self.records.append({
            "id": test_id,
            "method": method_name,
            "class": cls.__name__,
            "description": doc.split("\n")[0] if doc else method_name,
            "status": status,
            "duration_s": round(duration, 4),
            "tier": tier,
            "milestone": milestone,
            "error": error
        })


def discover_and_filter_tests(tier=None, milestone=None, feature=None):
    """Discover tests with optional filtering."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover in subdirectories
    subdirs = [
        "tier1_feature_coverage",
        "tier2_boundary_corner",
        "tier3_pairwise_combinations",
        "tier4_real_world_scenarios"
    ]

    for sdir in subdirs:
        if tier:
            tier_str = f"tier{tier}"
            if tier_str not in sdir:
                continue

        start_dir = os.path.join(E2E_DIR, sdir)
        if os.path.exists(start_dir):
            discovered = loader.discover(start_dir, pattern="test_*.py", top_level_dir=PROJECT_ROOT)
            suite.addTests(discovered)

    # Filter individual tests if milestone or feature specified
    if milestone or feature:
        filtered_suite = unittest.TestSuite()
        for test in _flatten_suite(suite):
            tid = test.id().lower()
            match_ms = True
            match_feat = True

            if milestone:
                ms_lower = milestone.lower()
                # Map features to milestones
                m1_feats = ["f01", "f02", "f03", "f04", "f05", "f06", "sim"]
                m2_feats = ["f07", "f08", "f09", "single_arm", "manip"]
                m3_feats = ["f10", "f11", "f12", "f13", "f14", "dual_arm"]
                m4_feats = ["f15", "f16", "f17", "f18", "vla", "cognitive"]
                m5_feats = ["f19", "f20", "f21", "f22", "dashboard", "scenemap"]

                if ms_lower == "m1":
                    match_ms = any(f in tid for f in m1_feats)
                elif ms_lower == "m2":
                    match_ms = any(f in tid for f in m2_feats)
                elif ms_lower == "m3":
                    match_ms = any(f in tid for f in m3_feats)
                elif ms_lower == "m4":
                    match_ms = any(f in tid for f in m4_feats)
                elif ms_lower == "m5":
                    match_ms = any(f in tid for f in m5_feats)

            if feature:
                feat_key = f"f{int(feature):02d}"
                match_feat = feat_key in tid

            if match_ms and match_feat:
                filtered_suite.addTest(test)
        return filtered_suite

    return suite


def _flatten_suite(suite):
    """Recursively yield individual test cases from nested suites."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten_suite(item)
        else:
            yield item


def run_e2e_suite(tier=None, milestone=None, feature=None, verbose=False):
    """Run E2E test suite and return structured summary."""
    suite = discover_and_filter_tests(tier=tier, milestone=milestone, feature=feature)
    result = E2ETestResult()
    start_time = time.time()
    suite.run(result)
    total_time = time.time() - start_time

    total = len(result.records)
    passed = sum(1 for r in result.records if r["status"] == "PASSED")
    failed = sum(1 for r in result.records if r["status"] == "FAILED")
    errors = sum(1 for r in result.records if r["status"] == "ERROR")
    skipped = sum(1 for r in result.records if r["status"] == "SKIPPED")

    # Tier Breakdown
    tier_counts = {}
    for r in result.records:
        t = r["tier"]
        tier_counts[t] = tier_counts.get(t, {"total": 0, "passed": 0, "failed": 0})
        tier_counts[t]["total"] += 1
        if r["status"] == "PASSED":
            tier_counts[t]["passed"] += 1
        elif r["status"] in ["FAILED", "ERROR"]:
            tier_counts[t]["failed"] += 1

    # Milestone Breakdown
    ms_counts = {}
    for r in result.records:
        m = r["milestone"]
        ms_counts[m] = ms_counts.get(m, {"total": 0, "passed": 0, "failed": 0})
        ms_counts[m]["total"] += 1
        if r["status"] == "PASSED":
            ms_counts[m]["passed"] += 1
        elif r["status"] in ["FAILED", "ERROR"]:
            ms_counts[m]["failed"] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "pass_rate": round(passed / total * 100, 2) if total > 0 else 0.0,
        "duration_s": round(total_time, 3),
        "tier_summary": tier_counts,
        "milestone_summary": ms_counts,
        "records": result.records
    }

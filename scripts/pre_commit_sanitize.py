from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS: Dict[str, re.Pattern[str]] = {
    "LOCAL_WINDOWS_USER_PATH": re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9_.-]+", re.IGNORECASE),
    "LOCAL_WINDOWS_GIT_PATH": re.compile(r"[A-Za-z]:\\git\\IsaacSim_Gemini", re.IGNORECASE),
    "LOCAL_WSL_MOUNT_PATH": re.compile(r"/mnt/[a-z]/git/IsaacSim_Gemini", re.IGNORECASE),
    "LOCAL_WSL_HOME_PATH": re.compile(r"/home/isaac/catkin_ws"),
    "INTERNAL_CORP_KEYWORD_SAIT": re.compile(r"\bSAIT\b"),
    "INTERNAL_CORP_KEYWORD_DEPOSITION_RECIPE": re.compile(r"\bdeposition_recipe_confidential\b", re.IGNORECASE),
    "RAW_GEMINI_API_KEY": re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"),
}


def scan_text_for_leaks(text: str, source_name: str = "<memory>") -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule_name, pattern in FORBIDDEN_PATTERNS.items():
            match = pattern.search(line)
            if match:
                violations.append(
                    {
                        "file": source_name,
                        "line": line_no,
                        "rule": rule_name,
                        "matched_snippet": match.group(0),
                    }
                )
    return violations


def scan_files(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    all_violations: List[Dict[str, Any]] = []
    for p in paths:
        if not p.exists() or not p.is_file():
            continue
        if p.name == "pre_commit_sanitize.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        all_violations.extend(scan_text_for_leaks(text, source_name=str(p)))
    return all_violations


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="STAMP Air-Gap Pre-Commit Sanitation Check")
    parser.add_argument("files", nargs="*", help="Files to scan for corporate keywords or local paths.")
    args = parser.parse_args(argv)

    if args.files:
        targets = [Path(f) for f in args.files]
    else:
        targets = list((_REPO_ROOT / "stamp").rglob("*.py")) + list(
            (_REPO_ROOT / "docs" / "blog_posts").rglob("*.md")
            if (_REPO_ROOT / "docs" / "blog_posts").exists()
            else []
        )

    violations = scan_files(targets)
    if violations:
        for v in violations:
            print(
                f"[SANITIZE BLOCK] {v['file']}:{v['line']} triggered {v['rule']} ({v['matched_snippet']})",
                file=sys.stderr,
            )
        return 1

    print(f"[SANITIZE PASS] Scanned {len(targets)} file(s) with 0 violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

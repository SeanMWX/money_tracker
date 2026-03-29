#!/usr/bin/env python3
"""Run the full money_tracker CLI test suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(TEST_DIR),
        "-p",
        "test_*.py",
        "-v",
    ]
    return subprocess.run(cmd, cwd=str(TEST_DIR.parent)).returncode


if __name__ == "__main__":
    raise SystemExit(main())

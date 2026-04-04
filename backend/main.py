#!/usr/bin/env python3
"""
Rubric entrypoint — run from the backend directory:

    python main.py --help
    python main.py --full-report
    python main.py --blast-radius --source pod-webfront --hops 3
    python main.py --source user-dev1 --target db-production
    python main.py --cycles
    python main.py --critical-node

Defaults --input to ../docs/mock-cluster-graph.json (repo root) when that file exists.
"""

from __future__ import annotations

import sys

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

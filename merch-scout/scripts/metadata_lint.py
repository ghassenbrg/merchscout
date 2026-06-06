#!/usr/bin/env python3
"""Validate Merch Scout metadata JSON."""

import argparse
import json
from pathlib import Path

from merch_scout_core import metadata_lint, print_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    data = json.loads(args.metadata.read_text(encoding="utf-8"))
    print_json(metadata_lint(data, run_dir=args.run_dir))


if __name__ == "__main__":
    main()

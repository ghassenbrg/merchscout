#!/usr/bin/env python3
"""Validate an existing Merch Scout run package end to end."""

import argparse
import json
from pathlib import Path

from merch_scout_core import print_json, validate_package, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--write", action="store_true", help="Overwrite output/validation/validation_summary.json.")
    args = parser.parse_args()
    metadata_path = args.run_dir / "output" / "metadata" / "merch_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    result = validate_package(args.run_dir, metadata)
    if args.write:
        write_json(args.run_dir / "output" / "validation" / "validation_summary.json", result)
    print_json(result)


if __name__ == "__main__":
    main()

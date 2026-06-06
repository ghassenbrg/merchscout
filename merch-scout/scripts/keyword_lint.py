#!/usr/bin/env python3
"""Lint Merch Scout keywords and listing terms."""

import argparse
import json
from pathlib import Path

from merch_scout_core import keyword_lint, print_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="*", help="Terms to lint when --metadata is not provided.")
    parser.add_argument("--metadata", type=Path, default=None, help="Path to merch_metadata.json.")
    args = parser.parse_args()
    if args.metadata:
        data = json.loads(args.metadata.read_text(encoding="utf-8"))
        result = keyword_lint(data)
    else:
        result = keyword_lint(args.terms)
    print_json(result)


if __name__ == "__main__":
    main()

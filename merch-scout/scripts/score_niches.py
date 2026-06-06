#!/usr/bin/env python3
"""Score Merch Scout niche candidates."""

import argparse
import json
from pathlib import Path

from merch_scout_core import print_json, score_niches, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Research JSON containing a candidates array.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = score_niches(data["candidates"])
    if args.out:
        write_json(args.out, result)
    print_json(result)


if __name__ == "__main__":
    main()

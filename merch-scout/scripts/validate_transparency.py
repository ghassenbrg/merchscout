#!/usr/bin/env python3
"""Validate real transparency and detect fake background issues."""

import argparse
from pathlib import Path

from merch_scout_core import canvas_presets, print_json, validate_transparency_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--canvas", choices=list(canvas_presets().keys()), default=None)
    args = parser.parse_args()
    print_json(validate_transparency_file(args.image, args.canvas))


if __name__ == "__main__":
    main()

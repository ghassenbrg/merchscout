#!/usr/bin/env python3
"""Validate PNG format, exact canvas dimensions, file size, alpha, and metadata."""

import argparse
from pathlib import Path

from merch_scout_core import canvas_presets, print_json, validate_png_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--canvas", choices=list(canvas_presets().keys()), default=None)
    parser.add_argument("--strict-srgb", action="store_true")
    args = parser.parse_args()
    print_json(validate_png_file(args.image, args.canvas, strict_srgb=args.strict_srgb))


if __name__ == "__main__":
    main()

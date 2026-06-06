#!/usr/bin/env python3
"""Place an existing transparent artwork onto an exact Merch Scout canvas."""

import argparse
from pathlib import Path

from merch_scout_core import canvas_presets, print_json, resize_canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--canvas", choices=list(canvas_presets().keys()), required=True)
    parser.add_argument("--scale", type=float, default=0.86)
    args = parser.parse_args()
    print_json(resize_canvas(args.source, args.output, args.canvas, scale=args.scale))


if __name__ == "__main__":
    main()

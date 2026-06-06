#!/usr/bin/env python3
"""Generate a single local demo/adapter design.

Production imagegen jobs are prepared by autopilot.py and finalized by
finalize_imagegen.py because Python cannot call Codex tools directly.
"""

import argparse
import json
from pathlib import Path

from merch_scout_core import canvas_presets, generate_design, print_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("concept", type=Path, help="Concept brief JSON.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--canvas", choices=list(canvas_presets().keys()), required=True)
    parser.add_argument("--option-index", type=int, default=1)
    parser.add_argument("--image-adapter-command", default=None)
    parser.add_argument("--no-demo-fallback", action="store_true")
    args = parser.parse_args()
    concept = json.loads(args.concept.read_text(encoding="utf-8"))
    print_json(
        generate_design(
            concept,
            args.canvas,
            args.output,
            option_index=args.option_index,
            adapter_command=args.image_adapter_command,
            allow_fallback=not args.no_demo_fallback,
        )
    )


if __name__ == "__main__":
    main()

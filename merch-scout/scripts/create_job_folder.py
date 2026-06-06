#!/usr/bin/env python3
"""Create a Merch Scout run folder with the required output/workspace structure."""

import argparse
from pathlib import Path

from merch_scout_core import DEFAULT_OUTPUT_ROOT, create_job_folder, print_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", help="Design slug or concept name.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timestamp", default=None)
    args = parser.parse_args()
    run_dir = create_job_folder(args.output_root, args.slug, timestamp=args.timestamp)
    print_json({"runDir": str(run_dir)})


if __name__ == "__main__":
    main()

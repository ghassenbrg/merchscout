#!/usr/bin/env python3
"""Finalize a Merch Scout run after Codex image_gen source images are saved."""

import argparse
from pathlib import Path

from merch_scout_core import finalize_imagegen_run, print_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    print_json(finalize_imagegen_run(args.run_dir))


if __name__ == "__main__":
    main()

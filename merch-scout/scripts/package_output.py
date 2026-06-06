#!/usr/bin/env python3
"""Write a package summary for a Merch Scout run folder."""

import argparse
from pathlib import Path

from merch_scout_core import package_output, print_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    print_json(package_output(args.run_dir))


if __name__ == "__main__":
    main()

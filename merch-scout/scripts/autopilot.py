#!/usr/bin/env python3
"""End-to-end Merch Scout autopilot."""

from merch_scout_core import autopilot_from_args, print_json


def main() -> None:
    print_json(autopilot_from_args())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run local trademark/IP/compliance adapter checks."""

import argparse

from merch_scout_core import marketplace_config, parse_csv, print_json, trademark_check


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="+", help="Terms, visible text, titles, brand candidates, or keywords to check.")
    parser.add_argument("--marketplaces", default="auto")
    args = parser.parse_args()
    result = trademark_check(args.terms, parse_csv(args.marketplaces, allowed=list(marketplace_config().keys())))
    print_json(result)


if __name__ == "__main__":
    main()

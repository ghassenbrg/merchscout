#!/usr/bin/env python3
"""Generate local market research candidates for Merch Scout."""

import argparse
from pathlib import Path

from merch_scout_core import canvas_presets, marketplace_config, parse_csv, print_json, research_candidates, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", default=None)
    parser.add_argument("--marketplaces", default="auto")
    parser.add_argument("--products", default="auto")
    parser.add_argument("--target-pool-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = research_candidates(
        niche=args.niche,
        marketplaces=parse_csv(args.marketplaces, allowed=list(marketplace_config().keys())),
        products=parse_csv(args.products, allowed=list(canvas_presets().keys())),
        target_pool_size=args.target_pool_size,
        seed=args.seed,
    )
    if args.out:
        write_json(args.out, result)
    print_json(result)


if __name__ == "__main__":
    main()

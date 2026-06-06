#!/usr/bin/env python3
"""Regenerate a Merch Scout report for an existing run folder."""

import argparse
import json
from pathlib import Path

from merch_scout_core import generate_report, print_json, write_text


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run = args.run_dir
    concept = _load(run / "workspace" / "concepts" / "concept_brief.json")
    metadata = _load(run / "output" / "metadata" / "merch_metadata.json")
    validation = _load(run / "output" / "validation" / "validation_summary.json")
    research = _load(run / "workspace" / "research" / "candidate_niches.json")
    scoring = _load(run / "workspace" / "research" / "scored_niches.json")
    compliance = _load(run / "workspace" / "compliance" / "trademark_checks.json")
    report = generate_report(run, concept, metadata, validation, research, scoring, compliance)
    out = run / "output" / "report" / "merch_report.md"
    write_text(out, report)
    print_json({"report": str(out)})


if __name__ == "__main__":
    main()

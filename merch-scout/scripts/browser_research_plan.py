#!/usr/bin/env python3
"""Generate browser research tasks from Merch Scout research_jobs.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from merch_scout_core import build_browser_research_tasks, print_json, write_json, write_text, _browser_research_plan_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Create browser research task files from research_jobs.json.")
    parser.add_argument("research", type=Path, help="Research directory or research_jobs.json.")
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args()

    jobs_path = args.research / "research_jobs.json" if args.research.is_dir() else args.research
    if not jobs_path.exists():
        raise SystemExit(f"Missing research jobs file: {jobs_path}")
    payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    tasks = build_browser_research_tasks(payload.get("jobs", []), payload.get("depth", "standard"), int(payload.get("requestedCount", 1) or 1))
    if args.print_only:
        print_json(tasks)
        return
    out_json = args.out_json or jobs_path.with_name("browser_research_tasks.json")
    out_md = args.out_md or jobs_path.with_name("browser_research_plan.md")
    write_json(out_json, tasks)
    write_text(out_md, _browser_research_plan_markdown(tasks))
    print_json({"status": "ok", "browserResearchTasks": str(out_json), "browserResearchPlan": str(out_md), "taskCount": tasks["taskCount"]})


if __name__ == "__main__":
    main()

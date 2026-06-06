#!/usr/bin/env python3
"""Copy a generated image into an imagegen job source path."""

import argparse
import shutil
from pathlib import Path

from merch_scout_core import load_json, print_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("job_id")
    parser.add_argument("generated_image", type=Path)
    args = parser.parse_args()

    manifest_path = args.run_dir / "workspace" / "processing" / "imagegen_jobs.json"
    manifest = load_json(manifest_path)
    matching = [job for job in manifest["jobs"] if job["jobId"] == args.job_id]
    if not matching:
        raise SystemExit(f"Unknown job id: {args.job_id}")
    target = args.run_dir / matching[0]["sourcePath"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.generated_image, target)
    matching[0]["status"] = "source_imported"
    write_json(manifest_path, manifest)
    print_json({"jobId": args.job_id, "sourcePath": str(target)})


if __name__ == "__main__":
    main()

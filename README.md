# Merch Scout

Local Codex skill for generating Amazon Merch on Demand / Merch by Amazon ready-for-human-review design packages.

The skill lives in [`merch-scout/`](./merch-scout) and can be installed as `$merch-scout` for Codex prompts.

Merch Scout v1 **does not upload anything**. It creates local packages containing transparent PNG files, strict metadata JSON, validation artifacts, preserved workspace notes, and a Markdown report for manual review.

Production artwork generation uses the Codex built-in `image_gen` tool through skill orchestration. The deterministic Pillow demo generator is only fallback/test mode.

Required compliance wording is used throughout generated reports:

```txt
No obvious trademark conflict found in checked sources.
This is not legal advice.
Human review is required before upload.
```

## Install

One-command install from this repo, regardless of current working directory:

```bash
./install.sh
```

The installer checks Python 3.10+, installs `merch-scout/requirements.txt`, and symlinks the skill to:

```txt
$HOME/.codex/skills/merch-scout
```

Dependencies are installed into a private virtual environment at:

```txt
$HOME/.codex/skills/.venvs/merch-scout
```

This avoids Homebrew/system Python `externally-managed-environment` errors.

The installer also creates a wrapper:

```txt
$HOME/.codex/bin/merch-scout
```

Use `./install.sh --copy` if you prefer a copied install, or `./install.sh --demo` to run a small demo after install.

After that, invoke it in Codex with:

```txt
Use $merch-scout to generate 10 ready-to-upload Amazon Merch on Demand designs.
```

Codex should load `merch-scout/SKILL.md` and run:

```bash
"$HOME/.codex/bin/merch-scout" autopilot --count 10 --output-root runs
```

That default command prepares imagegen jobs, then Codex calls `image_gen`, saves generated sources, and runs `finalize_imagegen.py`.

## Test Generation

Fast small-canvas local fallback test:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --generator demo \
  --count 1 \
  --products popsockets \
  --marketplaces US \
  --output-root runs
```

Production imagegen preparation:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --count 1 \
  --products standard_apparel \
  --marketplaces US,UK \
  --output-root runs
```

When it returns `status: awaiting_codex_imagegen`, call Codex `image_gen` for each job in:

```txt
<run>/workspace/processing/imagegen_jobs.json
```

Save or copy each generated image to the job `sourcePath`, then finalize:

```bash
"$HOME/.codex/bin/merch-scout" finalize-imagegen <run>
```

Directed run:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --count 3 \
  --marketplaces US,JP \
  --products standard_apparel,mugs \
  --niche "programmer cats" \
  --output-root runs
```

Each design package is written as:

```txt
runs/
  <timestamp>_<design-slug>/
    output/
      final/
      metadata/
      report/
      validation/
    workspace/
      research/
      compliance/
      concepts/
      candidates/
      processing/
```

## What It Produces

- `output/final/*.png`: exact Amazon canvas PNG files with transparent backgrounds where required.
- `output/metadata/merch_metadata.json`: strict upload-oriented metadata.
- `output/report/merch_report.md`: research, scoring, design direction, compliance, validation, and recommendation.
- `output/validation/validation_summary.json`: mechanical validation results.
- `workspace/`: research notes, scored/rejected candidates, concept brief, candidate options, compliance artifacts, and processing notes.

## Configuration

Common CLI flags:

```bash
--generator imagegen
--generator demo
--count 10
--marketplaces US,UK,JP
--products standard_apparel,mugs
--niche "programmer cats"
--variants-per-concept 3
--output-root runs
--image-adapter-command "python3 /absolute/path/to/adapter.py"
--no-demo-fallback
```

Environment variables:

```bash
MERCH_SCOUT_IMAGE_ADAPTER_CMD="python3 /absolute/path/to/adapter.py"
MERCH_SCOUT_IMAGE_ADAPTER_TIMEOUT=900
MERCH_SCOUT_CONFIG="/absolute/path/to/config.json"
```

The metadata contract is versioned and documented in `merch-scout/assets/metadata-schema.json`.

## Image Generation

Preferred production mode is `--generator imagegen`, which uses the Codex built-in `image_gen` system tool. The Python scripts prepare imagegen prompts and post-process the generated image sources into Amazon-ready transparent PNGs.

The fallback generator uses Pillow and local heuristics and should be selected explicitly with `--generator demo` for tests, offline smoke runs, or when imagegen is unavailable.

No paid API is required for demo mode.

## Optional External Adapters

Optional future adapters can improve evidence quality:

- Google Trends or third-party trend API,
- Keepa or similar Amazon rank/history data,
- Amazon allowed APIs or browser-assisted research within terms,
- USPTO, WIPO, EUIPO, UK IPO, JPO/J-PlatPat, and DPMA live trademark APIs.

When live adapters are unavailable, the skill records official/public source URLs and local risk linting. That is not a legal clearance.

### External Image Generation Adapter

Codex `image_gen` is preferred when running as a Codex skill. For non-Codex environments, Merch Scout also has an external adapter hook:

```bash
export MERCH_SCOUT_IMAGE_ADAPTER_CMD="python3 /absolute/path/to/your_adapter.py"
```

or:

```bash
python3 merch-scout/scripts/autopilot.py \
  --count 1 \
  --image-adapter-command "python3 /absolute/path/to/your_adapter.py"
```

The command receives JSON on stdin and must write an exact-size PNG to `outputPath`. See:

- `merch-scout/references/image-adapter-contract.md`
- `merch-scout/assets/adapter-config.example.json`
- `merch-scout/scripts/example_image_adapter.py`

If an adapter fails, the pipeline falls back to the demo generator unless `--no-demo-fallback` is set.

## Tests

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Run individual validators:

```bash
python3 merch-scout/scripts/validate_package.py path/to/run
python3 merch-scout/scripts/validate_png.py path/to/file.png --canvas standard_apparel
python3 merch-scout/scripts/validate_transparency.py path/to/file.png --canvas standard_apparel
python3 merch-scout/scripts/metadata_lint.py path/to/merch_metadata.json --run-dir path/to/run
python3 merch-scout/scripts/keyword_lint.py --metadata path/to/merch_metadata.json
```

## Human Review Still Required

Before Amazon upload, a human must verify:

- trademark/IP status in official databases for every phrase, title, brand, and keyword,
- visual originality and no protected likeness/logos/franchise references,
- spelling and text readability,
- marketplace localization quality,
- current Amazon Merch account product availability and upload UI limits,
- current Amazon content policy compliance.

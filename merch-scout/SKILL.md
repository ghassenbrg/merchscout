---
name: merch-scout
description: Use when generating Amazon Merch on Demand / Merch by Amazon ready-for-human-review design packages, including niche research, opportunity scoring, compliance checks, exact-canvas transparent PNG artwork, upload metadata JSON, validation artifacts, and a Markdown report. Invoke explicitly with $merch-scout for autopilot prompts such as generating multiple ready-to-upload designs; v1 never uploads automatically.
---

# Merch Scout

Merch Scout creates local, human-reviewable Amazon Merch on Demand design packages. It does not upload designs.

Core rule:

```txt
Research broadly.
Choose narrowly.
Design originally.
Validate mechanically.
Report honestly.
Never auto-upload.
Never claim legal safety.
```

## Quick Start

From this skill folder or the repository root:

```bash
python3 merch-scout/scripts/autopilot.py --count 1 --output-root runs
```

If installed under `~/.codex/skills`, this also works from any folder:

```bash
"$HOME/.codex/bin/merch-scout" autopilot --count 1 --output-root runs
```

For a constrained run:

```bash
python3 merch-scout/scripts/autopilot.py \
  --count 3 \
  --marketplaces US,JP \
  --products standard_apparel,mugs \
  --niche "programmer cats"
```

The output is one package per selected design:

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

## Operating Modes

- **Autopilot**: no niche/product/marketplace constraints. Researches a broad seed pool, scores candidates, rejects risky ideas, and produces the requested number of packages.
- **Directed**: user provides niche, marketplace, product, style, or text constraints. Follow the constraints unless compliance or validation fails.
- **Repair/review**: user provides an existing package or PNG/metadata file. Run validators and produce a repair plan or corrected package.

Always set `upload=false` and `humanReviewRequired=true` in generated metadata.

## Workflow

1. Parse the request into count, marketplaces, products, niches, variants, and upload intent.
2. Create run folders with `scripts/create_job_folder.py`.
3. Research and score niches with `scripts/research_market.py` and `scripts/score_niches.py`.
4. Run compliance and trademark/IP checks with `scripts/trademark_check.py` and `scripts/keyword_lint.py`.
5. Create concept briefs before artwork generation.
6. Production default: run `scripts/autopilot.py` with `--generator imagegen` (the default). This prepares `workspace/processing/imagegen_jobs.json`.
7. For every imagegen job, call Codex built-in `image_gen` with the job prompt. Save or copy each generated source file to its `sourcePath`.
8. Run `scripts/finalize_imagegen.py <run_dir>`. This removes chroma-key backgrounds when needed, places artwork on exact Amazon canvases, renders final text locally, exports transparent PNG, validates, and packages.
9. Use `--generator demo` only for tests, fallback, or when imagegen is unavailable.
10. Validate PNG dimensions, file format, transparency, fake backgrounds, metadata, and keywords.
11. Write `merch_metadata.json`, `merch_report.md`, and `validation_summary.json`.

## Required Wording

Use this compliance wording in metadata and reports:

```txt
No obvious trademark conflict found in checked sources.
This is not legal advice.
Human review is required before upload.
```

Do not say a design is legally safe.

## References

Open these only when needed:

- `references/amazon-product-dimensions.md`: product canvas presets and validation rules.
- `references/amazon-content-policy-summary.md`: policy risk categories and human-review notes.
- `references/marketplace-language-rules.md`: marketplace and localization rules.
- `references/niche-scoring-rubric.md`: scoring weights and rejection gates.
- `references/metadata-json-schema.md`: strict metadata shape.
- `references/design-generation-rules.md`: image generation, transparency, and typography rules.
- `references/compliance-checklist.md`: compliance workflow and official/public source adapters.
- `references/image-adapter-contract.md`: how to plug in real image generation.

## Scripts

Use `scripts/autopilot.py` for end-to-end runs. The other scripts are thin deterministic tools that can be run independently:

```txt
create_job_folder.py
research_market.py
score_niches.py
trademark_check.py
keyword_lint.py
metadata_lint.py
validate_png.py
validate_transparency.py
validate_package.py
resize_canvas.py
generate_design.py
finalize_imagegen.py
import_imagegen_artwork.py
example_image_adapter.py
generate_report.py
package_output.py
```

Codex `image_gen` is the preferred production generator. The deterministic demo generator is fallback/test mode only:

```bash
python3 merch-scout/scripts/autopilot.py --generator demo --count 1 --products popsockets --marketplaces US
```

## Imagegen Orchestration

When `autopilot.py` returns `status: awaiting_codex_imagegen`:

1. Open `workspace/processing/imagegen_jobs.json`.
2. For each job, call the built-in `image_gen` tool with `prompt`.
3. Save or copy the generated image into the run folder at `sourcePath`.
4. After all job source files exist, run:

```bash
python3 merch-scout/scripts/finalize_imagegen.py <run_dir>
```

The finalizer creates exact transparent PNG files, metadata, validation, package summary, and report.

External image generation, Google Trends, Keepa, Amazon, USPTO, WIPO, EUIPO, UK IPO, JPO/J-PlatPat, and DPMA integrations are optional adapters. If unavailable, the skill must still run end-to-end in fallback/test mode using local heuristics and the demo generator.

To plug in a real image generator, set:

```bash
export MERCH_SCOUT_IMAGE_ADAPTER_CMD="python3 /absolute/path/to/adapter.py"
```

or pass `--image-adapter-command`. The adapter receives JSON on stdin and must write a valid exact-canvas PNG to `outputPath`. If it fails, Merch Scout falls back to the demo generator unless `--no-demo-fallback` is used.

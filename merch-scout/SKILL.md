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
Optimize for quality, not speed.
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

## Depth Modes

Use `--depth standard` by default. Do not choose `quick` for normal production prompts.

- `quick`: local/demo-friendly smoke test mode. It may use local seed data and demo PNG generation. It must be labeled as fallback/demo in reports.
- `standard`: production default. Browse/search when internet tools are available, collect real evidence, compare multiple niches/products/marketplaces, then generate with Codex `imagegen`.
- `deep`: expanded production mode. Browse more extensively, compare more candidates and sub-niches, preserve more rejected ideas, use more image candidates, and perform deeper compliance/source review.

For `standard` and `deep`, do not proceed from research to image generation until `external_research.json` has enough real observations and sources to pass validation.

## Research Tool Model

The local Python CLI cannot browse the web or call Codex `image_gen` by itself. It creates research and image-generation job files, then Codex must use runtime tools to complete them.

Use these tools when available:

- Codex web search for broad demand, trend, keyword, marketplace, design-direction, and policy discovery.
- Browser/in-app browser for pages that require inspection beyond search snippets.
- Chrome plugin only when the user explicitly wants existing Chrome state, cookies, or logged-in pages. Do not use it to bypass access controls.
- Playwright for repeatable public-page screenshots or checks when allowed by site terms. Do not use it for bulk scraping, login bypass, CAPTCHA bypass, or automated harvesting.
- Official/public source pages for compliance/IP checks, especially USPTO, WIPO Global Brand Database, EUIPO, UK IPO, J-PlatPat/JPO, DPMAregister, and Amazon Merch on Demand policy/help pages.
- Codex `image_gen` after research evidence passes validation and `imagegen_jobs.json` exists.

No MCP server is required for v1. Optional MCP/API adapters for Google Trends, Keepa/Amazon data, or live trademark APIs may improve evidence later, but they are not required. If a tool is unavailable, explicitly label fallback/offline mode in `external_research.json` and in the report.

Free/no-key adapter command:

```bash
python3 merch-scout/scripts/free_research_adapters.py <research_dir>
```

Installed wrapper:

```bash
"$HOME/.codex/bin/merch-scout" research-free <research_dir>
```

Use this after `autopilot.py` creates `research_jobs.json`, then continue Codex/browser review for marketplace saturation and compliance nuance. The adapter uses Datamuse, Wikipedia/MediaWiki, Wikidata, DuckDuckGo Instant Answer, Wikimedia Pageviews, and public policy/source URLs. It does not scrape marketplace pages.

Browser research task files are created with each standard/deep research prep:

```txt
<research-run>/browser_research_tasks.json
<research-run>/browser_research_plan.md
```

Wrapper command:

```bash
"$HOME/.codex/bin/merch-scout" research-browser <research_dir>
```

When using Browser, Chrome, or Playwright, write observations into `external_research.json` with `sourceType`, `toolUsed`, `fetched=true`, URL, and concrete notes. Marketplace scans are for density/originality positioning only; never copy competitor artwork, listing titles, brands, layouts, tags, or phrases.

Evidence source categories:

```txt
marketplace
trend
keyword
trademark
policy
design_direction
```

Depth gates for one final design:

- `standard`: at least 6 usable observations, 10 usable sources, 2 sources per observation, and 3 source categories.
- `deep`: at least 12 usable observations, 24 usable sources, 3 sources per observation, and 4 source categories.

Scale up observations and sources when generating multiple final designs.

## Workflow

1. Parse the request into count, marketplaces, products, niches, variants, and upload intent.
2. Create run folders with `scripts/create_job_folder.py`.
3. Resolve depth. Default is `standard`.
4. Research and score niches with `scripts/research_market.py` and `scripts/score_niches.py`.
5. Run compliance and trademark/IP checks with `scripts/trademark_check.py` and `scripts/keyword_lint.py`.
6. Create concept briefs before artwork generation.
7. Production default: run `scripts/autopilot.py` with `--generator imagegen --depth standard` (both are defaults). This first returns `status: awaiting_codex_research` and writes `research_jobs.json`.
8. Complete the research jobs before image generation. Use web/browser/search where available, official/public sources where possible, no unauthorized scraping, and write findings to `external_research.json`.
9. Rerun `scripts/autopilot.py` with `--research-file <external_research.json>`. This validates evidence, scores candidates, and prepares `workspace/processing/imagegen_jobs.json`.
10. For every imagegen job, call Codex built-in `image_gen` with the job prompt. Save or copy each generated source file to its `sourcePath`.
11. Run `scripts/finalize_imagegen.py <run_dir>`. This removes chroma-key backgrounds when needed, places artwork on exact Amazon canvases, renders final text locally, exports transparent PNG, validates, and packages.
12. Use `--generator demo --depth quick` only for tests, fallback, or when imagegen is unavailable.
13. Validate PNG dimensions, file format, transparency, fake backgrounds, metadata, and keywords.
14. Write `merch_metadata.json`, `merch_report.md`, and `validation_summary.json`.

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
python3 merch-scout/scripts/autopilot.py --generator demo --depth quick --count 1 --products popsockets --marketplaces US
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

When `autopilot.py` returns `status: awaiting_codex_research`:

1. Open `research_jobs.json`.
2. Browse/search for demand, saturation, product fit, marketplace fit, keyword, design-direction, and compliance/IP evidence. Record actual queries and URLs.
3. Write observations to `external_research.json`.
4. Rerun:

```bash
python3 merch-scout/scripts/autopilot.py --count <N> --depth standard --output-root <runs> --research-file <external_research.json>
```

Do not call `image_gen` until research evidence has been written and the second autopilot run has produced imagegen jobs.

If browsing/search or image generation tools are unavailable, do not hide that. Set `fallbackOffline=true` and `fallbackReason` in `external_research.json`, use `--depth quick` only for smoke tests where appropriate, and ensure the final report contains:

```txt
This run used fallback/offline mode because external research/image generation was unavailable.
```

External image generation, Google Trends, Keepa, Amazon, USPTO, WIPO, EUIPO, UK IPO, JPO/J-PlatPat, and DPMA integrations are optional adapters. If unavailable, the skill must still run end-to-end in fallback/test mode using local heuristics and the demo generator.

To plug in a real image generator, set:

```bash
export MERCH_SCOUT_IMAGE_ADAPTER_CMD="python3 /absolute/path/to/adapter.py"
```

or pass `--image-adapter-command`. The adapter receives JSON on stdin and must write a valid exact-canvas PNG to `outputPath`. If it fails, Merch Scout falls back to the demo generator unless `--no-demo-fallback` is used.

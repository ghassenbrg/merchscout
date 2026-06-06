# Merch Scout

Local Codex skill for generating Amazon Merch on Demand / Merch by Amazon ready-for-human-review design packages.

The skill lives in [`merch-scout/`](./merch-scout) and can be installed as `$merch-scout` for Codex prompts.

Merch Scout v1 **does not upload anything**. It creates local packages containing transparent PNG files, strict metadata JSON, validation artifacts, preserved workspace notes, and a Markdown report for manual review.

Production artwork generation uses the Codex built-in `image_gen` tool through skill orchestration. The deterministic Pillow demo generator is only fallback/test mode. Merch Scout optimizes for research depth, originality, compliance caution, and human-reviewable output, not speed.

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

Use `./install.sh --copy` if you prefer a copied install, `./install.sh --skip-doctor` for quiet installs, or `./install.sh --demo` to run a small demo after install.

After that, invoke it in Codex with:

```txt
Use $merch-scout to generate 10 ready-to-upload Amazon Merch on Demand designs.
```

Codex should load `merch-scout/SKILL.md` and run:

```bash
"$HOME/.codex/bin/merch-scout" autopilot --count 10 --depth standard --output-root runs
```

`--depth standard` is the default. That command first prepares research jobs. Codex browses/searches where tools are available, fills `external_research.json` with real evidence, reruns autopilot with `--research-file`, then calls `image_gen`, saves generated sources, and runs `finalize_imagegen.py`.

## Depth Modes

```bash
--depth quick
--depth standard
--depth deep
```

- `quick`: local/demo-friendly smoke tests only. Use with `--generator demo`. Reports label fallback/demo usage.
- `standard`: default production mode. Requires real research evidence before scoring and image generation.
- `deep`: larger research queue, more source requirements, more rejected candidates, more image candidates, and stronger compliance review.

Standard/deep runs will reject an untouched or shallow `external_research.json` instead of silently continuing.

## How Deep Research Actually Works

Merch Scout is split into two parts:

- Python CLI: creates research jobs, validates evidence, scores niches, creates imagegen jobs, post-processes images, validates PNG/metadata, and writes reports.
- Codex agent: uses available runtime tools to browse/search, call `image_gen`, and copy generated image files into the run folder.

The Python CLI does not directly browse the web and does not directly call Codex `image_gen`. It creates enforceable work files so the Codex agent has to do those steps before the package can finish.

Deep production flow:

1. Run `autopilot --depth deep`.
2. The CLI writes `research_jobs.json` and `external_research.json`.
3. Codex reads `research_jobs.json`.
4. Codex uses web search and/or browser tools when available.
5. Codex records real queries, URLs, observations, rejected candidates, source categories, product fit, marketplace fit, and unresolved risks in `external_research.json`.
6. Rerun autopilot with `--research-file`.
7. The CLI rejects shallow evidence. Deep mode requires at least 12 usable observations, 24 usable sources, 3 sources per observation, and 4 source categories for a one-design run.
8. If evidence passes, the CLI creates `imagegen_jobs.json`.
9. Codex calls `image_gen` for each job and saves each generated source image to its `sourcePath`.
10. `finalize-imagegen` removes/uses transparency, places art on exact Amazon canvases, validates output, and writes the final report.

Research source categories used by the evidence validator:

```txt
marketplace
trend
keyword
trademark
policy
design_direction
```

Typical sources/tools Codex should use:

- Codex web search for marketplace demand, trend, keyword, design-direction, and public policy/source discovery.
- Browser plugin or in-app browser for pages that need inspection beyond search snippets.
- Official/public trademark and policy sources where possible: USPTO, WIPO Global Brand Database, EUIPO, UK IPO, J-PlatPat/JPO, DPMAregister, and Amazon Merch on Demand policy/help pages.
- Public marketplace/search result observations used only for positioning. Do not scrape in violation of site terms and do not copy competitor artwork, titles, brands, layouts, or phrases.

Free/no-key adapter suite installed with Merch Scout:

```txt
Datamuse keyword API
MediaWiki/Wikipedia OpenSearch API
Wikidata entity search API
DuckDuckGo Instant Answer API
Wikimedia Pageviews API
Public Amazon policy/source URLs
```

Run it after the first research-prep command:

```bash
"$HOME/.codex/bin/merch-scout" research-free runs/<timestamp>_research
```

Then continue:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --depth standard \
  --count 1 \
  --products standard_apparel \
  --marketplaces US,UK \
  --output-root runs \
  --research-file runs/<timestamp>_research/external_research.json
```

The free adapter improves the evidence file immediately, but it is not a replacement for human/Codex marketplace review. It does not scrape Amazon, Etsy, Redbubble, or other marketplace result pages.

MCP requirement:

```txt
No MCP server is required for v1.
```

Codex runtime web search/browser/imagegen are the preferred tools. Optional MCP/API adapters can improve data quality later, but they are not required to install Merch Scout.

Check local capability status:

```bash
"$HOME/.codex/bin/merch-scout" doctor
"$HOME/.codex/bin/merch-scout" doctor --json
```

## Browser / Chrome / Playwright Research

Every standard/deep research prep now writes:

```txt
<research-run>/browser_research_tasks.json
<research-run>/browser_research_plan.md
```

You can regenerate or inspect them with:

```bash
"$HOME/.codex/bin/merch-scout" research-browser runs/<timestamp>_research
"$HOME/.codex/bin/merch-scout" research-browser runs/<timestamp>_research --print-only
```

Tool choice:

- Browser plugin / in-app browser: default for public page inspection, Amazon search result scans, Google Trends, Openverse, policy pages, and screenshot-backed observations.
- Chrome plugin: use only when the user explicitly wants existing Chrome state, cookies, or logged-in pages. Do not use it to bypass access controls.
- Playwright: useful for repeatable public-page screenshots and checks when allowed by site terms. Do not use it for bulk scraping, login bypass, CAPTCHA bypass, or automated marketplace harvesting.
- Web search: best for broad discovery and source citation.

Browser research targets generated per niche:

- Amazon marketplace listing scans for visible crowding, repeated phrases, product types, and visual motifs.
- Google Trends and public trend searches.
- Keyword language checks.
- Openverse / image search / optional Pinterest visual direction scans for mood only, never copying.
- USPTO/WIPO/EUIPO/UK IPO/J-PlatPat/DPMA and Amazon policy URLs.

When Codex uses Browser/Chrome/Playwright, it must record observations into `external_research.json` sources like:

```json
{
  "title": "Amazon search observation",
  "url": "https://www.amazon.com/s?k=...",
  "sourceType": "marketplace",
  "toolUsed": "browser",
  "fetched": true,
  "note": "Top results appear crowded with exact phrase; avoid this wording."
}
```

Marketplace observations are for positioning only. Do not copy competitor artwork, listing titles, brands, layouts, tags, or phrases.

## Test Generation

Fast small-canvas local fallback test:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --generator demo \
  --depth quick \
  --count 1 \
  --products popsockets \
  --marketplaces US \
  --output-root runs
```

Production imagegen preparation:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --depth standard \
  --count 1 \
  --products standard_apparel \
  --marketplaces US,UK \
  --output-root runs
```

When it returns `status: awaiting_codex_research`, open:

```txt
<research-run>/research_jobs.json
```

Fill:

```txt
<research-run>/external_research.json
```

Then rerun:

```bash
"$HOME/.codex/bin/merch-scout" autopilot \
  --depth standard \
  --count 1 \
  --products standard_apparel \
  --marketplaces US,UK \
  --output-root runs \
  --research-file <research-run>/external_research.json
```

When the second run returns `status: awaiting_codex_imagegen`, call Codex `image_gen` for each job in:

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
  --depth standard \
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
--depth quick
--depth standard
--depth deep
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

Preferred production mode is `--generator imagegen --depth standard`, which uses the Codex built-in `image_gen` system tool after real research evidence has been collected. The Python scripts prepare imagegen prompts and post-process the generated image sources into Amazon-ready transparent PNGs.

The fallback generator uses Pillow and local heuristics and should be selected explicitly with `--generator demo --depth quick` for tests, offline smoke runs, or when imagegen is unavailable.

If browsing, imagegen, or external tools are unavailable, reports must state:

```txt
This run used fallback/offline mode because external research/image generation was unavailable.
```

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
  --generator demo \
  --depth quick \
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

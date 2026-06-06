# Image Generation Contract

Production default uses Codex built-in `image_gen`.

The local Python CLI cannot call Codex tools by itself. Instead, `autopilot.py --generator imagegen` prepares `workspace/processing/imagegen_jobs.json`; Codex reads those jobs, calls `image_gen`, saves sources to each `sourcePath`, then runs `finalize_imagegen.py`.

External adapter commands are still supported as an advanced alternative for non-Codex environments.

Configure one of:

```bash
export MERCH_SCOUT_IMAGE_ADAPTER_CMD="python3 /absolute/path/to/adapter.py"
export MERCH_SCOUT_CONFIG="/absolute/path/to/adapter-config.json"
python3 merch-scout/scripts/autopilot.py --image-adapter-command "python3 /absolute/path/to/adapter.py"
```

Adapter input is a single JSON object on stdin:

```json
{
  "concept": {},
  "canvas": "standard_apparel",
  "width": 4500,
  "height": 5400,
  "transparentRequired": true,
  "outputPath": "/absolute/path/to/output.png",
  "optionIndex": 1,
  "mustNotUpload": true
}
```

Adapter requirements:

- Write a PNG to `outputPath`.
- Match `width` and `height` exactly.
- Use real alpha transparency when `transparentRequired` is true.
- Do not include protected logos, franchise characters, public figures, or copied competitor layouts.
- Do not upload anything.
- Optional stdout can be JSON with adapter metadata.

If the adapter exits non-zero or produces an invalid PNG, Merch Scout uses the fallback demo generator unless `--no-demo-fallback` is passed.

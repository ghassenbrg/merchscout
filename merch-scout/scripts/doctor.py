#!/usr/bin/env python3
"""Report Merch Scout local and Codex-runtime capabilities."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]


def _exists(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists()}


def _pillow_status() -> dict[str, Any]:
    try:
        import PIL

        return {"installed": True, "version": getattr(PIL, "__version__", "unknown")}
    except Exception as exc:
        return {"installed": False, "error": str(exc)}


def build_report() -> dict[str, Any]:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    imagegen_skill = codex_home / "skills" / ".system" / "imagegen" / "SKILL.md"
    chroma_helper = codex_home / "skills" / ".system" / "imagegen" / "scripts" / "remove_chroma_key.py"
    playwright_skill = codex_home / "skills" / "playwright" / "SKILL.md"
    browser_skill_matches = sorted(
        str(path)
        for path in (codex_home / "plugins" / "cache").glob("openai-bundled/browser/*/skills/control-in-app-browser/SKILL.md")
    )
    chrome_skill_matches = sorted(
        str(path)
        for path in (codex_home / "plugins" / "cache").glob("openai-bundled/chrome/*/skills/control-chrome/SKILL.md")
    )
    installed_skill = codex_home / "skills" / "merch-scout"
    wrapper = codex_home / "bin" / "merch-scout"
    adapter_cmd = os.environ.get("MERCH_SCOUT_IMAGE_ADAPTER_CMD", "").strip()
    free_adapter = SKILL_ROOT / "scripts" / "free_research_adapters.py"

    return {
        "status": "ok",
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "pillow": _pillow_status(),
        },
        "localInstall": {
            "skillSource": _exists(SKILL_ROOT),
            "installedSkill": _exists(installed_skill),
            "commandWrapper": _exists(wrapper),
            "codexHome": str(codex_home),
        },
        "codexRuntimeCapabilities": {
            "imagegenSystemSkill": _exists(imagegen_skill),
            "imagegenChromaKeyHelper": _exists(chroma_helper),
            "browserPluginSkill": {"exists": bool(browser_skill_matches), "matches": browser_skill_matches[:8]},
            "chromePluginSkill": {"exists": bool(chrome_skill_matches), "matches": chrome_skill_matches[:8]},
            "playwrightSkill": _exists(playwright_skill),
            "playwrightCliOnPath": {"exists": bool(shutil.which("playwright")), "path": shutil.which("playwright")},
            "webSearchTool": {
                "shellDetectable": False,
                "expectedInCodex": True,
                "note": "The web search tool is exposed by the Codex runtime, not by this Python process. Merch Scout requires the agent to use it for standard/deep research when available.",
            },
            "imageGenTool": {
                "shellDetectable": False,
                "expectedInCodex": True,
                "note": "The image_gen tool is exposed by the Codex runtime. Python prepares imagegen_jobs.json; Codex calls image_gen and saves sourcePath files.",
            },
        },
        "optionalExternalTools": {
            "mcpRequired": False,
            "mcpNote": "No MCP server is required for v1. Codex web search/browser/image_gen are enough when available.",
            "freeNoKeyResearchAdapters": {
                "installed": free_adapter.exists(),
                "path": str(free_adapter),
                "providers": [
                    "Datamuse keyword API",
                    "MediaWiki/Wikipedia OpenSearch API",
                    "Wikidata entity search API",
                    "DuckDuckGo Instant Answer API",
                    "Wikimedia Pageviews API",
                    "Public Amazon policy/source URLs",
                ],
            },
            "imageAdapterCommand": {"configured": bool(adapter_cmd), "command": adapter_cmd or None},
            "codexCliOnPath": {"exists": bool(shutil.which("codex")), "path": shutil.which("codex")},
            "optionalPaidOrCredentialedAdapters": [
                "Google Trends or trend API adapter",
                "Keepa or Amazon data adapter used within terms",
                "USPTO/WIPO/EUIPO/UK IPO/J-PlatPat/DPMA live trademark API adapters",
            ],
        },
        "productionDepthRequirements": {
            "standard": {
                "minimumUsableObservations": 6,
                "minimumUsableSources": 10,
                "minimumSourcesPerObservation": 2,
                "minimumSourceTypes": 3,
                "webOrApiResearchRequired": True,
            },
            "deep": {
                "minimumUsableObservations": 12,
                "minimumUsableSources": 24,
                "minimumSourcesPerObservation": 3,
                "minimumSourceTypes": 4,
                "webOrApiResearchRequired": True,
            },
        },
        "importantLimitation": "The CLI validates and packages. It does not itself browse the web or call image_gen; Codex orchestrates those runtime tools from SKILL.md.",
    }


def print_human(report: dict[str, Any]) -> None:
    print("Merch Scout Doctor")
    print("===================")
    print(f"Python: {report['python']['version']} ({report['python']['executable']})")
    pillow = report["python"]["pillow"]
    print(f"Pillow: {'ok ' + pillow.get('version', '') if pillow.get('installed') else 'missing'}")
    print()
    print("Local install:")
    for label, item in report["localInstall"].items():
        if isinstance(item, dict):
            print(f"  {label}: {'ok' if item['exists'] else 'missing'} - {item['path']}")
        else:
            print(f"  {label}: {item}")
    print()
    print("Codex runtime capabilities:")
    runtime = report["codexRuntimeCapabilities"]
    for label in ["imagegenSystemSkill", "imagegenChromaKeyHelper"]:
        item = runtime[label]
        print(f"  {label}: {'ok' if item['exists'] else 'missing'} - {item['path']}")
    browser = runtime["browserPluginSkill"]
    print(f"  browserPluginSkill: {'ok' if browser['exists'] else 'not found locally'}")
    chrome = runtime["chromePluginSkill"]
    print(f"  chromePluginSkill: {'ok' if chrome['exists'] else 'not found locally'}")
    playwright_skill = runtime["playwrightSkill"]
    print(f"  playwrightSkill: {'ok' if playwright_skill['exists'] else 'not found locally'} - {playwright_skill['path']}")
    playwright_cli = runtime["playwrightCliOnPath"]
    print(f"  playwrightCliOnPath: {playwright_cli['path'] if playwright_cli['exists'] else 'not found'}")
    print("  webSearchTool: Codex-runtime tool, not shell-detectable")
    print("  imageGenTool: Codex-runtime tool, not shell-detectable")
    print()
    print("MCP/adapters:")
    optional = report["optionalExternalTools"]
    print(f"  MCP required: {optional['mcpRequired']}")
    print(f"  {optional['mcpNote']}")
    free = optional["freeNoKeyResearchAdapters"]
    print(f"  Free/no-key research adapters: {'ok' if free['installed'] else 'missing'}")
    for provider in free["providers"]:
        print(f"    - {provider}")
    adapter = optional["imageAdapterCommand"]
    print(f"  MERCH_SCOUT_IMAGE_ADAPTER_CMD: {adapter['command'] if adapter['configured'] else 'not configured'}")
    print()
    print("Production depth gates:")
    for depth, gates in report["productionDepthRequirements"].items():
        print(
            f"  {depth}: {gates['minimumUsableObservations']} observations, "
            f"{gates['minimumUsableSources']} sources, "
            f"{gates['minimumSourcesPerObservation']} source(s)/observation, "
            f"{gates['minimumSourceTypes']} source types"
        )
    print()
    print(report["importantLimitation"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Merch Scout local and Codex-runtime capabilities.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_human(report)


if __name__ == "__main__":
    main()

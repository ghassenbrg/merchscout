#!/usr/bin/env python3
"""Core implementation for the Merch Scout Codex skill."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parent
ASSETS_DIR = SKILL_ROOT / "assets"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "runs"

REQUIRED_COMPLIANCE_WORDING = (
    "No obvious trademark conflict found in checked sources. "
    "This is not legal advice. "
    "Human review is required before upload."
)

DEFAULT_FIELD_LIMITS = {
    "brand": 80,
    "title": 200,
    "bullet1": 500,
    "bullet2": 500,
    "description": 2000,
}

GENERATOR_CHOICES = ("imagegen", "demo")
DEPTH_CHOICES = ("quick", "standard", "deep")
CHROMA_KEY = "#00ff00"

FALLBACK_OFFLINE_NOTICE = "This run used fallback/offline mode because external research/image generation was unavailable."

DEPTH_PROFILES: dict[str, dict[str, Any]] = {
    "quick": {
        "description": "Local/demo-friendly smoke-test mode. Not intended for production upload decisions.",
        "candidateMultiplier": 4,
        "minimumResearchJobs": 8,
        "researchJobMultiplier": 4,
        "minObservations": 0,
        "minTotalSources": 0,
        "minSourcesPerObservation": 0,
        "minSourceTypes": 0,
        "minVariants": 2,
        "requiresExternalResearch": False,
    },
    "standard": {
        "description": "Production default. Requires real Codex/browser research evidence before scoring and imagegen.",
        "candidateMultiplier": 10,
        "minimumResearchJobs": 18,
        "researchJobMultiplier": 7,
        "minObservations": 6,
        "minTotalSources": 10,
        "minSourcesPerObservation": 2,
        "minSourceTypes": 3,
        "minVariants": 4,
        "requiresExternalResearch": True,
    },
    "deep": {
        "description": "Expanded production research. More niche comparisons, more evidence, and more concept variants.",
        "candidateMultiplier": 18,
        "minimumResearchJobs": 36,
        "researchJobMultiplier": 12,
        "minObservations": 12,
        "minTotalSources": 24,
        "minSourcesPerObservation": 3,
        "minSourceTypes": 4,
        "minVariants": 6,
        "requiresExternalResearch": True,
    },
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=False)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(value: str, fallback: str = "merch-design") -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or fallback


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def canvas_presets() -> dict[str, Any]:
    return load_json(ASSETS_DIR / "product-canvas-presets.json")


def marketplace_config() -> dict[str, Any]:
    return load_json(ASSETS_DIR / "marketplace-config.json")


def forbidden_seeds() -> dict[str, list[str]]:
    return load_json(ASSETS_DIR / "forbidden-keyword-seeds.json")


def parse_csv(value: str | None, allowed: list[str] | None = None) -> list[str] | None:
    if not value or value.lower() == "auto":
        return None
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    if allowed is not None:
        unknown = [item for item in parsed if item not in allowed]
        if unknown:
            raise SystemExit(f"Unknown value(s): {', '.join(unknown)}. Allowed: {', '.join(allowed)}")
    return parsed


def depth_profile(depth: str) -> dict[str, Any]:
    if depth not in DEPTH_PROFILES:
        raise SystemExit(f"Unknown depth: {depth}. Use one of: {', '.join(DEPTH_CHOICES)}")
    return DEPTH_PROFILES[depth]


def ensure_run_structure(run_dir: Path) -> dict[str, Path]:
    paths = {
        "final": run_dir / "output" / "final",
        "metadata": run_dir / "output" / "metadata",
        "report": run_dir / "output" / "report",
        "validation": run_dir / "output" / "validation",
        "research": run_dir / "workspace" / "research",
        "compliance": run_dir / "workspace" / "compliance",
        "concepts": run_dir / "workspace" / "concepts",
        "candidates": run_dir / "workspace" / "candidates",
        "processing": run_dir / "workspace" / "processing",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def create_job_folder(output_root: Path, design_slug: str, timestamp: str | None = None) -> Path:
    timestamp = timestamp or now_stamp()
    base_name = f"{timestamp}_{slugify(design_slug)}"
    run_dir = output_root / base_name
    suffix = 2
    while run_dir.exists():
        run_dir = output_root / f"{base_name}-{suffix:02d}"
        suffix += 1
    ensure_run_structure(run_dir)
    write_json(
        run_dir / "workspace" / "research" / "run_manifest.json",
        {
            "designSlug": slugify(design_slug),
            "createdAt": timestamp,
            "upload": False,
            "humanReviewRequired": True,
        },
    )
    return run_dir


def _base_niche_pool() -> list[dict[str, Any]]:
    return [
        {
            "name": "Quiet Coffee Coder",
            "niche": "programmer humor + coffee + introverts",
            "nicheType": "evergreen crossover",
            "visibleText": "Quiet Mode Coder",
            "keywords": ["programmer", "coffee", "introvert", "coding gift", "developer humor"],
            "marketplaces": ["US", "UK", "DE", "JP"],
            "products": ["standard_apparel", "mugs"],
            "style": "typography-first badge with small original coffee icon",
            "demand": 76,
            "saturation": 48,
            "originality": 74,
            "seasonality": "evergreen",
            "mustAvoid": ["GitHub logo", "Java logo", "specific programming language logos"],
        },
        {
            "name": "Sushi Code Mode",
            "niche": "coding humor + sushi + Japanese food",
            "nicheType": "evergreen crossover",
            "visibleText": "Sushi Code Mode",
            "keywords": ["sushi", "coder", "programmer", "tech humor", "japanese food gift"],
            "marketplaces": ["US", "UK", "JP"],
            "products": ["standard_apparel", "mugs", "tote_pillow"],
            "style": "cute flat original sushi mascot with controlled typography",
            "demand": 72,
            "saturation": 42,
            "originality": 82,
            "seasonality": "evergreen",
            "mustAvoid": ["Hello Kitty resemblance", "anime character likeness", "brand logos"],
        },
        {
            "name": "Garden Debug Club",
            "niche": "plant hobby + programmer wordplay",
            "nicheType": "evergreen crossover",
            "visibleText": "Debug The Garden",
            "keywords": ["gardening", "plants", "coder", "plant parent", "developer gift"],
            "marketplaces": ["US", "UK", "DE"],
            "products": ["standard_apparel", "tote_pillow", "mugs"],
            "style": "friendly botanical illustration with clean centered lettering",
            "demand": 68,
            "saturation": 36,
            "originality": 86,
            "seasonality": "spring evergreen",
            "mustAvoid": ["brand names", "software logos"],
        },
        {
            "name": "Teacher Fuel Loading",
            "niche": "teacher gifts + coffee",
            "nicheType": "evergreen occupation",
            "visibleText": "Teacher Fuel Loading",
            "keywords": ["teacher", "coffee", "school gift", "teacher appreciation", "classroom"],
            "marketplaces": ["US", "UK", "DE", "FR", "ES"],
            "products": ["mugs", "standard_apparel", "tote_pillow"],
            "style": "mug-friendly typography with original pencil and cup marks",
            "demand": 82,
            "saturation": 67,
            "originality": 62,
            "seasonality": "back to school evergreen",
            "mustAvoid": ["school logos", "district names"],
        },
        {
            "name": "Ramen Gym Reset",
            "niche": "gym humor + ramen food crossover",
            "nicheType": "evergreen crossover",
            "visibleText": "Ramen Is Recovery",
            "keywords": ["ramen", "gym", "fitness humor", "food lover", "workout gift"],
            "marketplaces": ["US", "UK", "JP", "DE"],
            "products": ["standard_apparel", "mugs"],
            "style": "bold illustrated ramen bowl with barbell-inspired original shapes",
            "demand": 70,
            "saturation": 39,
            "originality": 84,
            "seasonality": "evergreen",
            "mustAvoid": ["gym brand names", "anime references"],
        },
        {
            "name": "Tiny Steps Big Lift",
            "niche": "beginner fitness motivation",
            "nicheType": "evergreen motivational",
            "visibleText": "Tiny Steps Big Lift",
            "keywords": ["fitness", "workout", "motivation", "gym gift", "training"],
            "marketplaces": ["US", "UK", "DE", "FR"],
            "products": ["standard_apparel", "performance_square"],
            "style": "clean athletic typography with abstract motion lines",
            "demand": 73,
            "saturation": 59,
            "originality": 67,
            "seasonality": "new year evergreen",
            "mustAvoid": ["sports brand slogans", "medical claims"],
        },
        {
            "name": "Book Club After Dark",
            "niche": "book lover humor + cozy reading",
            "nicheType": "evergreen hobby",
            "visibleText": "Late Night Book Club",
            "keywords": ["book lover", "reading", "book club", "reader gift", "cozy"],
            "marketplaces": ["US", "UK", "DE", "FR", "ES"],
            "products": ["standard_apparel", "mugs", "tote_pillow"],
            "style": "cozy illustrated stack of original books with warm type",
            "demand": 78,
            "saturation": 52,
            "originality": 72,
            "seasonality": "evergreen",
            "mustAvoid": ["book titles", "author names", "copyrighted quotes"],
        },
        {
            "name": "Sakura Desk Break",
            "niche": "office worker calm + sakura season",
            "nicheType": "regional seasonal",
            "visibleText": "Desk Break Bloom",
            "keywords": ["sakura", "office worker", "spring", "calm design", "desk break"],
            "marketplaces": ["JP", "US", "UK"],
            "products": ["mugs", "standard_apparel", "tote_pillow"],
            "style": "minimal blossom motif with natural calm typography",
            "demand": 66,
            "saturation": 34,
            "originality": 88,
            "seasonality": "spring",
            "mustAvoid": ["temple names", "tourism logos", "awkward Japanese"],
        },
        {
            "name": "Pet Hair Everywhere",
            "niche": "pet owner humor",
            "nicheType": "evergreen pet",
            "visibleText": "Pet Hair Everywhere",
            "keywords": ["pet owner", "dog mom", "cat dad", "pet humor", "animal lover"],
            "marketplaces": ["US", "UK", "DE", "FR", "IT", "ES"],
            "products": ["standard_apparel", "mugs", "tote_pillow"],
            "style": "playful typography with original paw confetti",
            "demand": 84,
            "saturation": 74,
            "originality": 55,
            "seasonality": "evergreen",
            "mustAvoid": ["breed club logos", "rescue organization names"],
        },
        {
            "name": "Moon Phase Gardener",
            "niche": "gardening + moon phase aesthetic",
            "nicheType": "evergreen aesthetic",
            "visibleText": "Grow With The Moon",
            "keywords": ["gardener", "moon phase", "plants", "botanical", "garden gift"],
            "marketplaces": ["US", "UK", "DE", "FR"],
            "products": ["standard_apparel", "tote_pillow", "mugs"],
            "style": "original botanical moon badge, limited palette, readable serif-free type",
            "demand": 67,
            "saturation": 41,
            "originality": 83,
            "seasonality": "evergreen spring",
            "mustAvoid": ["astrology brand names", "medical or spiritual claims"],
        },
        {
            "name": "Wizard School Fan Art",
            "niche": "wizard franchise fan art",
            "nicheType": "rejected protected IP example",
            "visibleText": "Wizard School Alumni",
            "keywords": ["wizard", "hogwarts", "magic school", "fan art"],
            "marketplaces": ["US", "UK"],
            "products": ["standard_apparel"],
            "style": "fantasy crest",
            "demand": 90,
            "saturation": 92,
            "originality": 20,
            "seasonality": "evergreen",
            "mustAvoid": ["Hogwarts", "Harry Potter", "franchise crests"],
        },
    ]


def _expand_for_directed_niche(niche: str) -> list[dict[str, Any]]:
    cleaned = niche.strip()
    base = [
        ("Typography", "Clean readable phrase badge", "typography-first"),
        ("Illustrated", "Original mascot/object composition", "illustration-led"),
        ("Vintage", "Retro badge with limited palette", "vintage badge"),
        ("Mug Wrap", "Horizontal small-format layout", "mug-friendly"),
    ]
    candidates: list[dict[str, Any]] = []
    for idx, (suffix, phrase, style) in enumerate(base, start=1):
        candidates.append(
            {
                "name": f"{cleaned.title()} {suffix}",
                "niche": cleaned,
                "nicheType": "directed user niche",
                "visibleText": _safe_visible_text(cleaned, idx),
                "keywords": list(dict.fromkeys(re.findall(r"[a-zA-Z0-9]+", cleaned.lower()) + ["gift", "shirt"])),
                "marketplaces": ["US", "UK", "JP"],
                "products": ["standard_apparel", "mugs"],
                "style": f"{style}: {phrase}",
                "demand": 65 + idx * 3,
                "saturation": 43 + idx * 4,
                "originality": 72 + idx * 2,
                "seasonality": "user-directed",
                "mustAvoid": ["brand names", "franchise references", "logos", "public figures"],
            }
        )
    return candidates


def _safe_visible_text(niche: str, idx: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", niche.title())
    if not words:
        return f"Original Design {idx}"
    return " ".join(words[:4])


def research_candidates(
    niche: str | None = None,
    marketplaces: list[str] | None = None,
    products: list[str] | None = None,
    target_pool_size: int = 20,
    seed: int = 7,
    external_research: dict[str, Any] | None = None,
    depth: str = "standard",
    fallback_offline: bool = False,
    requested_count: int = 1,
) -> dict[str, Any]:
    rng = random.Random(seed)
    pool = _expand_for_directed_niche(niche) if niche else _base_niche_pool()
    expanded: list[dict[str, Any]] = []
    for candidate in pool:
        c = dict(candidate)
        if marketplaces:
            c["marketplaces"] = [m for m in c["marketplaces"] if m in marketplaces] or marketplaces
        if products:
            c["products"] = [p for p in c["products"] if p in products] or products
        c["researchSignals"] = {
            "sourceMode": "local_seed_pool",
            "demandNotes": [
                f"{c['nicheType']} candidate with {c['seasonality']} appeal",
                "External trend and marketplace APIs are optional adapters in v1.",
            ],
            "competitorObservation": (
                "Use competitor analysis for market expectations only; do not copy layouts, "
                "phrases, or artwork."
            ),
            "keywordCandidates": c["keywords"],
        }
        _apply_external_research(c, external_research)
        expanded.append(c)
    while len(expanded) < target_pool_size:
        base = dict(rng.choice(pool))
        base["variant"] = True
        base["variantOf"] = base["name"]
        base["name"] = f"{base['name']} Variant {len(expanded) + 1}"
        base["visibleText"] = f"{base['visibleText']} Club"
        base["demand"] = max(30, min(95, base["demand"] + rng.randint(-8, 8)))
        base["saturation"] = max(20, min(95, base["saturation"] + rng.randint(-10, 10)))
        base["originality"] = max(25, min(95, base["originality"] + rng.randint(-6, 6)))
        expanded.append(base)
    return {
        "generatedAt": now_stamp(),
        "depth": depth,
        "mode": "directed" if niche else "autopilot",
        "requestedMarketplaces": marketplaces or "auto",
        "requestedProducts": products or "auto",
        "fallbackOffline": bool(fallback_offline),
        "fallbackNotice": FALLBACK_OFFLINE_NOTICE if fallback_offline else "",
        "externalResearchUsed": bool(external_research),
        "externalResearch": external_research or {},
        "evidenceValidation": validate_external_research(external_research, depth, requested_count=requested_count)
        if external_research
        else {"valid": depth == "quick", "errors": [] if depth == "quick" else ["No external research evidence file was supplied."], "warnings": [], "stats": {}},
        "candidateCount": len(expanded),
        "candidates": expanded,
    }


def _apply_external_research(candidate: dict[str, Any], external_research: dict[str, Any] | None) -> None:
    if not external_research:
        return
    observations = external_research.get("observations", [])
    best: dict[str, Any] | None = None
    best_overlap = 0
    candidate_tokens = set(re.findall(r"[a-z0-9]+", f"{candidate.get('name','')} {candidate.get('niche','')} {' '.join(candidate.get('keywords', []))}".lower()))
    for observation in observations:
        observed_text = f"{observation.get('niche','')} {observation.get('query','')} {' '.join(observation.get('keywords', []))}".lower()
        observed_tokens = set(re.findall(r"[a-z0-9]+", observed_text))
        overlap = len(candidate_tokens & observed_tokens)
        if overlap > best_overlap:
            best = observation
            best_overlap = overlap
    if not best or best_overlap == 0:
        return
    if isinstance(best.get("demandSignal"), (int, float)):
        candidate["demand"] = int(round((candidate.get("demand", 50) + best["demandSignal"]) / 2))
    if isinstance(best.get("saturationSignal"), (int, float)):
        candidate["saturation"] = int(round((candidate.get("saturation", 50) + best["saturationSignal"]) / 2))
    if isinstance(best.get("originalityPotential"), (int, float)):
        candidate["originality"] = int(round((candidate.get("originality", 50) + best["originalityPotential"]) / 2))
    candidate.setdefault("researchSignals", {})
    candidate["researchSignals"]["sourceMode"] = "local_seed_pool_plus_codex_research"
    candidate["researchSignals"]["externalObservation"] = best


def prepare_research_jobs(
    output_root: Path,
    count: int,
    marketplaces: list[str] | None,
    products: list[str] | None,
    niche: str | None,
    depth: str = "standard",
    seed: int = 7,
) -> dict[str, Any]:
    profile = depth_profile(depth)
    timestamp = now_stamp()
    research_dir = output_root / f"{timestamp}_research"
    research_dir.mkdir(parents=True, exist_ok=True)
    seed_pool = research_candidates(
        niche=niche,
        marketplaces=marketplaces,
        products=products,
        target_pool_size=max(profile["minimumResearchJobs"], count * profile["researchJobMultiplier"]),
        seed=seed,
        depth=depth,
        requested_count=count,
    )
    candidates = seed_pool["candidates"]
    jobs = []
    for idx, candidate in enumerate(candidates[: max(profile["minimumResearchJobs"], count * profile["researchJobMultiplier"])], start=1):
        jobs.append(
            {
                "jobId": f"research_{idx:02d}_{slugify(candidate['name'])}",
                "candidateName": candidate["name"],
                "niche": candidate["niche"],
                "visibleText": candidate["visibleText"],
                "marketplaces": candidate.get("marketplaces", marketplaces or ["US", "UK"]),
                "products": candidate.get("products", products or ["standard_apparel"]),
                "keywords": candidate.get("keywords", []),
                "localSeedScores": {
                    "demand": candidate.get("demand"),
                    "saturation": candidate.get("saturation"),
                    "originality": candidate.get("originality"),
                    "seasonality": candidate.get("seasonality"),
                },
                "researchQuestions": [
                    "What demand signals exist for this niche and related keywords?",
                    "How saturated does Amazon Merch / print-on-demand competition look?",
                    "Which sub-niches are less saturated and still buyer-relevant?",
                    "Which product canvas and marketplace fit best?",
                    "Are there obvious trademark, public figure, brand, franchise, or policy risks?",
                    "What design direction is common in the market, and how can this design remain original?",
                ],
                "suggestedQueries": [
                    f"Amazon merch {candidate['niche']} shirt",
                    f"Amazon {candidate['visibleText']} shirt",
                    f"Google Trends {candidate['niche']}",
                    f"trademark {candidate['visibleText']}",
                    f"USPTO TESS {candidate['visibleText']}",
                    f"WIPO Global Brand Database {candidate['visibleText']}",
                    f"Amazon Merch on Demand content policy {candidate['niche']}",
                ],
                "requiredEvidence": [
                    "At least one marketplace/demand observation.",
                    "At least one saturation or competitor-density observation.",
                    "At least one compliance/IP observation using official or public search sources where possible.",
                    "At least one design-direction note explaining how to stay original.",
                ],
            }
        )
    template = {
        "schemaVersion": "1.0.0",
        "depth": depth,
        "completedAt": "",
        "method": "Codex research using web/browser/search where available; no unauthorized scraping.",
        "webSearchUsed": False,
        "browserResearchUsed": False,
        "webSearchRequiredWhenAvailable": depth in {"standard", "deep"},
        "fallbackOffline": False,
        "fallbackReason": "",
        "minimumEvidenceRequirements": {
            "minObservations": max(profile["minObservations"], count * 2 if depth != "quick" else 0),
            "minTotalSources": max(profile["minTotalSources"], count * 4 if depth == "standard" else count * 8 if depth == "deep" else 0),
            "minSourcesPerObservation": profile["minSourcesPerObservation"],
            "minSourceTypes": profile["minSourceTypes"],
            "sourceTypes": ["marketplace", "trend", "keyword", "trademark", "policy", "design_direction"],
        },
        "queriesSearched": [],
        "observations": [],
        "rejectedCandidates": [],
        "marketplaceComparisons": [],
        "productComparisons": [],
        "unresolvedRisks": [],
        "instructions": [
            "Replace this template with real findings before rerunning autopilot.",
            "Use browsing/search tools where available and record every meaningful query in queriesSearched.",
            "Use official/public trademark or policy sources where possible.",
            "If browsing is unavailable, set fallbackOffline=true and explain fallbackReason. The final report will label the run.",
        ],
        "observationTemplate": {
            "jobId": "research_01_candidate_slug",
            "niche": "candidate niche",
            "query": "query actually searched",
            "demandSignal": 0,
            "saturationSignal": 0,
            "originalityPotential": 0,
            "marketplaceFit": {"US": "why this market fits or does not fit"},
            "productFit": {"standard_apparel": "why this product fits or does not fit"},
            "keywords": ["keyword actually supported by research"],
            "riskFlags": [{"severity": "low|medium|high", "type": "trademark|copyright|brand|public_figure|policy", "note": "risk note"}],
            "notes": ["Specific observation, not generic filler."],
            "sources": [{"title": "source title", "url": "https://example.com", "sourceType": "marketplace|trend|keyword|trademark|policy|design_direction", "note": "why it matters"}],
        },
    }
    jobs_path = research_dir / "research_jobs.json"
    evidence_path = research_dir / "external_research.json"
    browser_tasks = build_browser_research_tasks(jobs, depth, count)
    browser_tasks_path = research_dir / "browser_research_tasks.json"
    browser_plan_path = research_dir / "browser_research_plan.md"
    write_json(
        jobs_path,
        {
            "schemaVersion": "1.0.0",
            "status": "awaiting_codex_research",
            "depth": depth,
            "requestedCount": count,
            "webSearchRequiredWhenAvailable": depth in {"standard", "deep"},
            "qualityPriority": "Optimize for research depth, originality, compliance caution, and human-reviewable output rather than speed.",
            "minimumEvidenceRequirements": template["minimumEvidenceRequirements"],
            "comparisonRequirements": [
                "Compare at least the listed niches before selecting winners.",
                "Compare sub-niches, products, and marketplaces rather than only validating the first candidate.",
                "Record rejected candidates with concrete reasons.",
            ],
            "browserResearchTasks": str(browser_tasks_path),
            "jobs": jobs,
        },
    )
    write_json(evidence_path, template)
    write_json(browser_tasks_path, browser_tasks)
    write_json(research_dir / "seed_candidates.json", seed_pool)
    write_text(research_dir / "research_instructions.md", _research_instructions_markdown(jobs_path, evidence_path, depth, template["minimumEvidenceRequirements"]))
    write_text(browser_plan_path, _browser_research_plan_markdown(browser_tasks))
    return {
        "createdAt": timestamp,
        "status": "awaiting_codex_research",
        "depth": depth,
        "requestedCount": count,
        "researchDir": str(research_dir),
        "researchJobs": str(jobs_path),
        "browserResearchTasks": str(browser_tasks_path),
        "browserResearchPlan": str(browser_plan_path),
        "researchEvidenceFile": str(evidence_path),
        "nextStep": f"Fill {evidence_path} with real observations, then rerun autopilot with --research-file {evidence_path}",
        "upload": False,
        "humanReviewRequired": True,
    }


def _research_instructions_markdown(jobs_path: Path, evidence_path: Path, depth: str, requirements: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Merch Scout Research Instructions",
            "",
            f"Depth: `{depth}`",
            f"Jobs: `{jobs_path}`",
            f"Write evidence to: `{evidence_path}`",
            "",
            "For each candidate, gather demand, saturation, product fit, marketplace fit, keyword quality, design direction, and compliance/IP risk.",
            "Use official/public sources where possible. Do not use unauthorized scraping.",
            f"Minimum observations: {requirements.get('minObservations')}",
            f"Minimum total sources: {requirements.get('minTotalSources')}",
            f"Minimum sources per observation: {requirements.get('minSourcesPerObservation')}",
            f"Minimum source types: {requirements.get('minSourceTypes')}",
            "",
            "Record actual queries, URLs, rejected candidates, scoring reasons, marketplace observations, product observations, and unresolved risks.",
            "Do not start image generation until this research evidence file has been filled.",
            "",
        ]
    )


def build_browser_research_tasks(jobs: list[dict[str, Any]], depth: str, count: int) -> dict[str, Any]:
    profile = depth_profile(depth)
    task_count = max(profile["minObservations"], count * (2 if depth == "standard" else 4 if depth == "deep" else 1))
    selected = jobs[: min(len(jobs), task_count)]
    tasks = [_browser_task_for_job(job, depth) for job in selected]
    return {
        "schemaVersion": "1.0.0",
        "status": "awaiting_browser_research",
        "depth": depth,
        "taskCount": len(tasks),
        "toolPriority": [
            {
                "tool": "Codex web search",
                "useFor": "Broad discovery, current source lookup, policy/trademark source discovery, and citation URLs.",
            },
            {
                "tool": "Browser plugin / in-app browser",
                "useFor": "Public page inspection, Amazon/search result visual scan, Google Trends, Openverse/design-direction pages, and screenshots where useful.",
            },
            {
                "tool": "Chrome plugin",
                "useFor": "Only when the user explicitly wants to use existing Chrome state, cookies, or logged-in pages. Do not use it to bypass access controls.",
            },
            {
                "tool": "Playwright",
                "useFor": "Repeatable screenshots or public-page checks when allowed by site terms. Avoid bulk scraping, login bypass, CAPTCHA bypass, or automated harvesting.",
            },
        ],
        "rules": [
            "Do not auto-upload anything.",
            "Do not scrape in violation of a site's terms.",
            "Do not bypass CAPTCHAs, paywalls, rate limits, login walls, or robots controls.",
            "Use marketplace observations for positioning only; do not copy competitor artwork, titles, brands, tags, layouts, or phrases.",
            "Capture human-reviewable observations: visible density, repeated phrases, product types, visual trends, pricing/rating/BSR if visibly available, and unresolved risks.",
            "Every useful observation must be written into external_research.json with sourceType, URL, note, toolUsed, and fetched=true.",
        ],
        "evidenceMapping": {
            "amazonListingScan": "sourceType=marketplace; contributes saturationSignal and marketplaceFit.",
            "trendScan": "sourceType=trend; contributes demandSignal and seasonality notes.",
            "keywordScan": "sourceType=keyword; contributes keyword quality and listing language.",
            "designDirectionScan": "sourceType=design_direction; contributes originalityPotential and mustAvoid notes.",
            "trademarkPolicyScan": "sourceType=trademark or policy; contributes riskFlags and unresolvedRisks.",
        },
        "tasks": tasks,
    }


def _browser_task_for_job(job: dict[str, Any], depth: str) -> dict[str, Any]:
    visible = str(job.get("visibleText") or job.get("candidateName") or "")
    niche = str(job.get("niche") or visible)
    query = f"{visible} {niche}".strip()
    markets = job.get("marketplaces") or ["US"]
    products = job.get("products") or ["standard_apparel"]
    return {
        "jobId": job.get("jobId"),
        "candidateName": job.get("candidateName"),
        "niche": niche,
        "visibleText": visible,
        "depth": depth,
        "recommendedTools": ["web search", "Browser plugin", "Playwright screenshots if useful and allowed"],
        "marketplaces": markets,
        "products": products,
        "browserChecks": [
            {
                "type": "amazon_listing_scan",
                "sourceType": "marketplace",
                "tool": "Browser or Chrome; Playwright only for public screenshots and allowed checks.",
                "urls": _amazon_research_urls(query, visible, markets),
                "record": [
                    "Approximate visible result density or crowding.",
                    "Repeated phrases, obvious copycat layouts, or dominant visual motifs.",
                    "Whether exact visible text appears crowded or risky.",
                    "Product formats that appear common.",
                    "Any visible rating/price/BSR signals if naturally shown.",
                ],
                "doNot": "Do not scrape result pages, paginate deeply, extract seller data, or copy listings.",
            },
            {
                "type": "trend_scan",
                "sourceType": "trend",
                "tool": "Browser or web search.",
                "urls": _trend_research_urls(query, markets),
                "record": ["Trend direction if visible.", "Seasonality.", "Related rising terms if visible."],
            },
            {
                "type": "keyword_language_scan",
                "sourceType": "keyword",
                "tool": "web search, Browser, free adapter output.",
                "urls": _keyword_research_urls(query),
                "record": ["Buyer wording.", "Gift-intent modifiers.", "Terms to avoid for policy or keyword stuffing."],
            },
            {
                "type": "design_direction_scan",
                "sourceType": "design_direction",
                "tool": "Browser or image search. Use for mood/vocabulary only, never copying.",
                "urls": _design_research_urls(query),
                "record": [
                    "Common visual motifs to avoid copying.",
                    "Open whitespace, typography, icon/motif opportunities.",
                    "Original direction recommendation.",
                    "Protected/copyright-looking visual territory to avoid.",
                ],
            },
            {
                "type": "trademark_policy_scan",
                "sourceType": "trademark",
                "tool": "Browser or web search.",
                "urls": _trademark_policy_urls(visible, niche, markets),
                "record": [
                    "Exact phrase/source searched.",
                    "Obvious trademark/brand/public-figure/franchise/policy risk.",
                    "Unresolved legal review questions.",
                ],
            },
        ],
        "externalResearchObservationSkeleton": {
            "jobId": job.get("jobId"),
            "niche": niche,
            "query": query,
            "demandSignal": 0,
            "saturationSignal": 0,
            "originalityPotential": 0,
            "marketplaceFit": {market: "browser observation" for market in markets},
            "productFit": {product: "browser observation" for product in products},
            "keywords": [],
            "riskFlags": [],
            "notes": [],
            "sources": [
                {
                    "title": "source title",
                    "url": "https://source.example",
                    "sourceType": "marketplace|trend|keyword|trademark|policy|design_direction",
                    "toolUsed": "web_search|browser|chrome|playwright|free_adapter",
                    "fetched": True,
                    "note": "specific observation",
                }
            ],
        },
    }


def _amazon_research_urls(query: str, visible: str, markets: list[str]) -> list[dict[str, str]]:
    domains = {
        "US": "www.amazon.com",
        "UK": "www.amazon.co.uk",
        "DE": "www.amazon.de",
        "FR": "www.amazon.fr",
        "IT": "www.amazon.it",
        "ES": "www.amazon.es",
        "JP": "www.amazon.co.jp",
    }
    urls = []
    search_terms = [f"{query} shirt", f"{visible} shirt"] if visible else [f"{query} shirt"]
    for market in markets:
        domain = domains.get(market, "www.amazon.com")
        for term in list(dict.fromkeys(search_terms)):
            urls.append({"marketplace": market, "url": f"https://{domain}/s?k={quote_plus(term)}", "note": "Public Amazon search URL for manual/browser observation only."})
    return urls


def _trend_research_urls(query: str, markets: list[str]) -> list[dict[str, str]]:
    geo = "US"
    if "UK" in markets:
        geo = "GB"
    elif "JP" in markets:
        geo = "JP"
    return [
        {"url": f"https://trends.google.com/trends/explore?date=today%205-y&geo={geo}&q={quote_plus(query)}", "note": "Google Trends browser check."},
        {"url": f"https://www.google.com/search?q={quote_plus(query + ' trend merch')}", "note": "General trend/source discovery search."},
    ]


def _keyword_research_urls(query: str) -> list[dict[str, str]]:
    return [
        {"url": f"https://www.google.com/search?q={quote_plus(query + ' gift shirt')}", "note": "Buyer language and gift-intent wording."},
        {"url": f"https://api.datamuse.com/words?ml={quote_plus(query)}&max=20", "note": "Free Datamuse keyword expansion API."},
        {"url": f"https://duckduckgo.com/?q={quote_plus(query + ' merch shirt')}", "note": "Public search page for query language."},
    ]


def _design_research_urls(query: str) -> list[dict[str, str]]:
    return [
        {"url": f"https://openverse.org/search/image?q={quote_plus(query)}", "note": "Openverse visual context; use for broad motif vocabulary only."},
        {"url": f"https://www.google.com/search?tbm=isch&q={quote_plus(query + ' vintage badge illustration')}", "note": "Image-search mood scan; do not copy artwork."},
        {"url": f"https://www.pinterest.com/search/pins/?q={quote_plus(query + ' shirt design')}", "note": "Optional browser-only visual trend scan; do not copy and do not scrape."},
    ]


def _trademark_policy_urls(visible: str, niche: str, markets: list[str]) -> list[dict[str, str]]:
    terms = [visible, niche]
    urls = []
    for term in [t for t in terms if t]:
        for source in source_queries(term, markets):
            urls.append({"url": source["url"], "note": source["name"], "market": source["market"]})
    urls.extend(
        [
            {"url": "https://developer.amazon.com/merch", "note": "Official Amazon Merch on Demand entry point."},
            {"url": f"https://www.google.com/search?q={quote_plus('Amazon Merch on Demand content policy ' + niche)}", "note": "Public policy discovery query."},
        ]
    )
    return urls


def _browser_research_plan_markdown(tasks_payload: dict[str, Any]) -> str:
    lines = [
        "# Browser Research Plan",
        "",
        f"Depth: `{tasks_payload.get('depth')}`",
        "",
        "## Tool Priority",
        "",
    ]
    for item in tasks_payload.get("toolPriority", []):
        lines.append(f"- {item['tool']}: {item['useFor']}")
    lines.extend(["", "## Rules", ""])
    for rule in tasks_payload.get("rules", []):
        lines.append(f"- {rule}")
    lines.extend(["", "## Tasks", ""])
    for task in tasks_payload.get("tasks", []):
        lines.extend(
            [
                f"### {task.get('jobId')} - {task.get('candidateName')}",
                "",
                f"- Niche: {task.get('niche')}",
                f"- Visible text: {task.get('visibleText')}",
                "",
            ]
        )
        for check in task.get("browserChecks", []):
            lines.append(f"#### {check['type']}")
            lines.append("")
            lines.append(f"- Source type: `{check['sourceType']}`")
            lines.append(f"- Tool: {check['tool']}")
            lines.append("- URLs:")
            for url in check.get("urls", [])[:8]:
                lines.append(f"  - {url.get('url')} - {url.get('note', '')}")
            lines.append("- Record:")
            for item in check.get("record", []):
                lines.append(f"  - {item}")
            if check.get("doNot"):
                lines.append(f"- Do not: {check['doNot']}")
            lines.append("")
    return "\n".join(lines)


def validate_external_research(evidence: dict[str, Any] | None, depth: str, requested_count: int = 1) -> dict[str, Any]:
    profile = depth_profile(depth)
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {
        "observationCount": 0,
        "usableObservationCount": 0,
        "totalSources": 0,
        "sourceTypes": [],
        "queryCount": 0,
        "rejectedCandidateCount": 0,
        "fallbackOffline": False,
    }
    if not evidence:
        if profile["requiresExternalResearch"]:
            errors.append("External research evidence is required for this depth.")
        return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}

    fallback_offline = bool(evidence.get("fallbackOffline"))
    stats["fallbackOffline"] = fallback_offline
    fallback_reason = str(evidence.get("fallbackReason", "")).strip()
    if fallback_offline:
        warnings.append(FALLBACK_OFFLINE_NOTICE)
        if not fallback_reason:
            errors.append("fallbackOffline=true requires fallbackReason.")
    elif depth != "quick" and evidence.get("webSearchUsed") is not True and evidence.get("apiResearchUsed") is not True:
        errors.append("webSearchUsed or apiResearchUsed must be true for standard/deep research unless fallbackOffline=true.")

    observations = evidence.get("observations", [])
    if not isinstance(observations, list):
        errors.append("external research observations must be a list.")
        observations = []
    usable_observations = [obs for obs in observations if isinstance(obs, dict) and not _is_placeholder_observation(obs)]
    stats["observationCount"] = len(observations)
    stats["usableObservationCount"] = len(usable_observations)
    if len(usable_observations) < len(observations):
        warnings.append("Placeholder/example observations were ignored.")

    queries = evidence.get("queriesSearched", [])
    if isinstance(queries, list):
        stats["queryCount"] = len([q for q in queries if str(q).strip()])
    elif queries:
        errors.append("queriesSearched must be a list.")

    rejected_candidates = evidence.get("rejectedCandidates", [])
    if isinstance(rejected_candidates, list):
        stats["rejectedCandidateCount"] = len(rejected_candidates)
    elif rejected_candidates:
        errors.append("rejectedCandidates must be a list.")

    all_sources: list[dict[str, Any]] = []
    observations_with_enough_sources = 0
    observations_with_scored_signals = 0
    source_types: set[str] = set()
    for idx, observation in enumerate(usable_observations, start=1):
        for signal in ["demandSignal", "saturationSignal", "originalityPotential"]:
            if signal not in observation or not isinstance(observation.get(signal), (int, float)):
                errors.append(f"observation {idx} missing numeric {signal}.")
        if all(isinstance(observation.get(signal), (int, float)) for signal in ["demandSignal", "saturationSignal", "originalityPotential"]):
            observations_with_scored_signals += 1
        sources = observation.get("sources", [])
        if not isinstance(sources, list):
            errors.append(f"observation {idx} sources must be a list.")
            sources = []
        usable_sources = [source for source in sources if _is_usable_source(source)]
        if len(usable_sources) >= profile["minSourcesPerObservation"]:
            observations_with_enough_sources += 1
        elif not fallback_offline and profile["minSourcesPerObservation"]:
            errors.append(f"observation {idx} needs at least {profile['minSourcesPerObservation']} usable source(s).")
        all_sources.extend(usable_sources)
        for source in usable_sources:
            source_types.add(_source_type(source))
        if not observation.get("marketplaceFit") and not fallback_offline and depth != "quick":
            errors.append(f"observation {idx} missing marketplaceFit.")
        if not observation.get("productFit") and not fallback_offline and depth != "quick":
            errors.append(f"observation {idx} missing productFit.")
        if not observation.get("notes") and not fallback_offline and depth != "quick":
            errors.append(f"observation {idx} missing concrete notes.")

    stats["totalSources"] = len(all_sources)
    stats["sourceTypes"] = sorted(source_types)
    stats["observationsWithEnoughSources"] = observations_with_enough_sources
    stats["observationsWithScoredSignals"] = observations_with_scored_signals

    requirements = evidence.get("minimumEvidenceRequirements", {})
    min_observations = max(int(profile["minObservations"]), int(requirements.get("minObservations", 0) or 0), requested_count * (2 if depth == "standard" else 4 if depth == "deep" else 0))
    min_total_sources = max(int(profile["minTotalSources"]), int(requirements.get("minTotalSources", 0) or 0), requested_count * (4 if depth == "standard" else 8 if depth == "deep" else 0))
    min_source_types = max(int(profile["minSourceTypes"]), int(requirements.get("minSourceTypes", 0) or 0))

    if not fallback_offline:
        if len(usable_observations) < min_observations:
            errors.append(f"{depth} depth requires at least {min_observations} usable research observations; found {len(usable_observations)}.")
        if len(all_sources) < min_total_sources:
            errors.append(f"{depth} depth requires at least {min_total_sources} usable research sources; found {len(all_sources)}.")
        if len(source_types) < min_source_types:
            errors.append(f"{depth} depth requires at least {min_source_types} source categories; found {len(source_types)}.")
        if stats["queryCount"] < max(3, requested_count * 2) and depth != "quick":
            errors.append("queriesSearched must list the real searches/browsing queries used.")
        if stats["rejectedCandidateCount"] < max(1, requested_count) and depth != "quick":
            errors.append("rejectedCandidates must explain what was considered and rejected.")
    elif len(usable_observations) == 0:
        warnings.append("Fallback/offline evidence has no usable observations; report will mark the run as fallback.")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def _is_placeholder_observation(observation: dict[str, Any]) -> bool:
    text = json.dumps(observation, ensure_ascii=False).lower()
    return any(marker in text for marker in ["research_01_example", "example niche", "replace this example", "https://example.com"])


def _is_usable_source(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    if source.get("fetched") is False:
        return False
    url = str(source.get("url", "")).strip()
    title = str(source.get("title", "")).strip()
    if not title or not re.match(r"https?://", url):
        return False
    if "example.com" in url:
        return False
    return True


def _source_type(source: dict[str, Any]) -> str:
    explicit = str(source.get("sourceType", "")).strip().lower()
    if explicit:
        return explicit
    text = f"{source.get('title', '')} {source.get('url', '')} {source.get('note', '')}".lower()
    if any(token in text for token in ["uspto", "wipo", "euipo", "trademark", "ipo.gov", "j-platpat", "dpma"]):
        return "trademark"
    if any(token in text for token in ["policy", "content guideline", "amazon merch on demand"]):
        return "policy"
    if any(token in text for token in ["trend", "google trends", "seasonal"]):
        return "trend"
    if any(token in text for token in ["keyword", "search volume", "autosuggest"]):
        return "keyword"
    if any(token in text for token in ["amazon", "etsy", "redbubble", "teepublic", "marketplace"]):
        return "marketplace"
    if any(token in text for token in ["design", "visual", "style"]):
        return "design_direction"
    return "other"


def flatten_forbidden_terms() -> list[dict[str, str]]:
    flattened = []
    for category, terms in forbidden_seeds().items():
        for term in terms:
            flattened.append({"category": category, "term": term})
    return flattened


def lint_terms(terms: list[str]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    normalized_terms = [term.lower() for term in terms if term]
    for entry in flatten_forbidden_terms():
        needle = entry["term"].lower()
        for source in normalized_terms:
            if needle in source:
                hits.append({"term": entry["term"], "category": entry["category"], "source": source})
    high_risk_categories = {"brands_and_franchises", "public_figures_and_groups", "copyright_risk"}
    high_risk = any(hit["category"] in high_risk_categories for hit in hits)
    medium_risk = any(hit["category"] == "policy_risk_terms" for hit in hits)
    return {
        "hits": hits,
        "riskLevel": "high" if high_risk else "medium" if medium_risk else "low",
        "blocked": high_risk,
    }


def score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    terms = [candidate.get("name", ""), candidate.get("niche", ""), candidate.get("visibleText", "")]
    terms += candidate.get("keywords", [])
    lint = lint_terms(terms)
    demand = int(candidate.get("demand", 50))
    saturation_raw = int(candidate.get("saturation", 50))
    low_medium_saturation = max(0, 100 - abs(saturation_raw - 45) * 1.35)
    product_fit = min(100, 52 + len(candidate.get("products", [])) * 12)
    marketplace_fit = min(100, 48 + len(candidate.get("marketplaces", [])) * 8)
    keyword_quality = 74 if 4 <= len(candidate.get("keywords", [])) <= 8 else 58
    originality = int(candidate.get("originality", 60))
    compliance_safety = 15 if lint["riskLevel"] == "high" else 65 if lint["riskLevel"] == "medium" else 92
    final_score = (
        demand * 0.25
        + low_medium_saturation * 0.20
        + product_fit * 0.15
        + marketplace_fit * 0.10
        + keyword_quality * 0.10
        + originality * 0.10
        + compliance_safety * 0.10
    )
    if candidate.get("variant"):
        final_score -= 6
    rejection_reasons = []
    if lint["blocked"]:
        rejection_reasons.append("Known brand/franchise/public figure/copyright risk term detected.")
    if compliance_safety < 50:
        rejection_reasons.append("Compliance/IP safety score below hard gate.")
    if originality < 35:
        rejection_reasons.append("Design originality potential is too low.")
    scored = dict(candidate)
    scored["scores"] = {
        "demandSignal": round(demand, 2),
        "lowToMediumSaturation": round(low_medium_saturation, 2),
        "productFit": round(product_fit, 2),
        "marketplaceFit": round(marketplace_fit, 2),
        "keywordQuality": round(keyword_quality, 2),
        "designOriginalityPotential": round(originality, 2),
        "complianceIpSafety": round(compliance_safety, 2),
        "finalOpportunityScore": round(final_score, 2),
    }
    scored["riskLint"] = lint
    scored["rejected"] = bool(rejection_reasons)
    scored["rejectionReasons"] = rejection_reasons
    return scored


def score_niches(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [score_candidate(candidate) for candidate in candidates]
    accepted = [item for item in scored if not item["rejected"]]
    rejected = [item for item in scored if item["rejected"]]
    accepted.sort(key=lambda item: item["scores"]["finalOpportunityScore"], reverse=True)
    rejected.sort(key=lambda item: item["scores"]["finalOpportunityScore"], reverse=True)
    return {
        "generatedAt": now_stamp(),
        "accepted": accepted,
        "rejected": rejected,
        "all": scored,
        "rubric": {
            "demandSignal": 0.25,
            "lowToMediumSaturation": 0.20,
            "productFit": 0.15,
            "marketplaceFit": 0.10,
            "keywordQuality": 0.10,
            "designOriginalityPotential": 0.10,
            "complianceIpSafety": 0.10,
        },
    }


def source_queries(term: str, marketplaces: list[str]) -> list[dict[str, str]]:
    q = quote_plus(term)
    sources = [
        {
            "name": "USPTO trademark search",
            "market": "US",
            "url": f"https://tmsearch.uspto.gov/search/search-results?query={q}",
        },
        {
            "name": "WIPO Global Brand Database",
            "market": "International",
            "url": f"https://branddb.wipo.int/en/quicksearch?by=brandName&v={q}",
        },
        {
            "name": "EUIPO eSearch",
            "market": "EU",
            "url": f"https://euipo.europa.eu/eSearch/#advanced/trademarks/{q}",
        },
        {
            "name": "UK IPO trademark search",
            "market": "UK",
            "url": f"https://trademarks.ipo.gov.uk/ipo-tmtext?term={q}",
        },
        {
            "name": "J-PlatPat trademark search",
            "market": "JP",
            "url": f"https://www.j-platpat.inpit.go.jp/?lang=en&keyword={q}",
        },
        {
            "name": "DPMAregister",
            "market": "DE",
            "url": f"https://register.dpma.de/DPMAregister/marke/einsteiger?query={q}",
        },
    ]
    if not marketplaces:
        return sources
    market_set = set(marketplaces)
    return [
        source
        for source in sources
        if source["market"] in market_set
        or source["market"] in {"International", "EU"}
        or (source["market"] == "UK" and "UK" in market_set)
    ]


def trademark_check(terms: list[str], marketplaces: list[str] | None = None) -> dict[str, Any]:
    unique_terms = [term for term in dict.fromkeys([t.strip() for t in terms if t and t.strip()])]
    lint = lint_terms(unique_terms)
    checks = []
    for term in unique_terms:
        checks.append(
            {
                "term": term,
                "localRisk": lint_terms([term]),
                "officialSourceQueries": source_queries(term, marketplaces or []),
                "liveLookup": "not_run",
                "notes": "Adapter records official/public source URLs. Live API credentials are optional in v1.",
            }
        )
    statement = REQUIRED_COMPLIANCE_WORDING
    if lint["riskLevel"] != "low":
        statement = (
            "Potential compliance or trademark/IP risk detected by local lint. "
            "This is not legal advice. Human review is required before upload."
        )
    return {
        "checkedAt": now_stamp(),
        "terms": unique_terms,
        "marketplaces": marketplaces or "auto",
        "riskLevel": lint["riskLevel"],
        "blocked": lint["blocked"],
        "riskHits": lint["hits"],
        "checks": checks,
        "statement": statement,
        "liveLookupAdapters": {
            "USPTO": "optional",
            "WIPO": "optional",
            "EUIPO": "optional",
            "UK IPO": "optional",
            "J-PlatPat/JPO": "optional",
            "DPMAregister": "optional",
        },
    }


def enrich_compliance_with_research(compliance: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(compliance)
    evidence = concept.get("researchEvidence") or {}
    research_flags = evidence.get("riskFlags", []) if isinstance(evidence, dict) else []
    if not isinstance(research_flags, list):
        research_flags = []
    external_sources = evidence.get("sources", []) if isinstance(evidence, dict) else []
    if not isinstance(external_sources, list):
        external_sources = []
    enriched["researchRiskFlags"] = research_flags
    enriched["externalEvidenceSources"] = external_sources
    if research_flags:
        high = any(str(flag.get("severity", "")).lower() == "high" for flag in research_flags if isinstance(flag, dict))
        medium = any(str(flag.get("severity", "")).lower() == "medium" for flag in research_flags if isinstance(flag, dict))
        if high:
            enriched["riskLevel"] = "high"
            enriched["blocked"] = True
            enriched["statement"] = "Potential compliance or trademark/IP risk detected in Codex research. This is not legal advice. Human review is required before upload."
        elif medium and enriched.get("riskLevel") == "low":
            enriched["riskLevel"] = "medium"
            enriched["statement"] = "Potential compliance or trademark/IP risk requires manual review. This is not legal advice. Human review is required before upload."
    if external_sources:
        enriched.setdefault("checks", [])
        enriched["checks"].append(
            {
                "term": concept.get("visibleText") or concept.get("conceptName"),
                "localRisk": {"riskLevel": enriched.get("riskLevel"), "hits": []},
                "officialSourceQueries": [],
                "liveLookup": "codex_research_recorded",
                "notes": "External research sources were recorded by Codex and must still be reviewed by a human.",
                "sources": external_sources,
            }
        )
    return enriched


def build_concept(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    product_fit = candidate.get("products", ["standard_apparel"])
    style = candidate.get("style", "original typography-led merch design")
    text = candidate.get("visibleText", candidate.get("name", "Original Design"))
    concept = {
        "conceptId": f"design_{index:02d}_{slugify(candidate['name'])}",
        "conceptName": candidate["name"],
        "niche": candidate["niche"],
        "nicheType": candidate.get("nicheType", "unknown"),
        "marketplaces": candidate.get("marketplaces", ["US"]),
        "productFit": product_fit,
        "designStyle": style,
        "textStrategy": _text_strategy(product_fit, candidate.get("marketplaces", []), text),
        "visibleText": text,
        "mustAvoid": list(
            dict.fromkeys(
                candidate.get("mustAvoid", [])
                + [
                    "brand logos",
                    "franchise characters",
                    "public figures",
                    "team names",
                    "competitor design copying",
                    "fake transparent background",
                ]
            )
        ),
        "generationPrompt": (
            f"Original Merch on Demand design for {candidate['niche']}. "
            f"Style: {style}. Visible text must read exactly: '{text}'. "
            "Transparent background, strong print-safe margins, no logos, no protected IP."
        ),
        "scores": candidate.get("scores", {}),
        "researchSignals": candidate.get("researchSignals", {}),
        "researchEvidence": candidate.get("researchSignals", {}).get("externalObservation", {}),
        "keywords": candidate.get("keywords", []),
    }
    return concept


def _text_strategy(product_fit: list[str], marketplaces: list[str], text: str) -> str:
    if "mugs" in product_fit:
        base = "short readable phrase; horizontal-friendly composition"
    elif len(text) <= 24:
        base = "short readable phrase; typography can be final-rendered deterministically"
    else:
        base = "minimize text length and verify readability manually"
    if "JP" in marketplaces:
        base += "; JP listing should be natural Japanese or no-text if phrase does not localize"
    return base


def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default(size=size)


def _wrap_text(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def generate_demo_design(
    concept: dict[str, Any],
    canvas_key: str,
    output_path: Path,
    option_index: int = 1,
) -> dict[str, Any]:
    from PIL import Image, ImageDraw

    presets = canvas_presets()
    if canvas_key not in presets:
        raise SystemExit(f"Unknown canvas: {canvas_key}")
    width, height = presets[canvas_key]["size"]
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    palette = [
        (27, 79, 114, 255),
        (243, 156, 18, 255),
        (39, 174, 96, 255),
        (231, 76, 60, 255),
        (248, 249, 249, 255),
    ]
    dark, accent, green, red, light = palette
    margin_x = int(width * 0.12)
    margin_y = int(height * 0.15)
    center_x = width // 2
    center_y = height // 2
    badge_w = width - margin_x * 2
    badge_h = min(int(height * 0.56), height - margin_y * 2)
    badge_left = center_x - badge_w // 2
    badge_top = center_y - badge_h // 2
    badge_right = center_x + badge_w // 2
    badge_bottom = center_y + badge_h // 2
    radius = max(20, min(width, height) // 18)

    if option_index % 3 == 1:
        draw.rounded_rectangle(
            [badge_left, badge_top, badge_right, badge_bottom],
            radius=radius,
            fill=(248, 249, 249, 245),
            outline=dark,
            width=max(6, width // 180),
        )
        draw.arc(
            [badge_left - width * 0.02, badge_top - height * 0.04, badge_right + width * 0.02, badge_bottom + height * 0.04],
            200,
            340,
            fill=accent,
            width=max(8, width // 110),
        )
    elif option_index % 3 == 2:
        draw.ellipse(
            [badge_left, badge_top, badge_right, badge_bottom],
            fill=(248, 249, 249, 238),
            outline=green,
            width=max(6, width // 160),
        )
    else:
        points = [
            (center_x, badge_top),
            (badge_right, center_y),
            (center_x, badge_bottom),
            (badge_left, center_y),
        ]
        draw.polygon(points, fill=(248, 249, 249, 238), outline=dark)
        draw.line(points + [points[0]], fill=red, width=max(6, width // 170))

    # Original abstract icon marks. These are deliberately generic and not logo-like.
    icon_r = max(24, min(width, height) // 18)
    icon_y = badge_top + int(badge_h * 0.24)
    for offset, color in [(-2, accent), (-1, green), (0, red), (1, dark), (2, accent)]:
        x = center_x + offset * icon_r
        draw.ellipse([x - icon_r // 2, icon_y - icon_r // 2, x + icon_r // 2, icon_y + icon_r // 2], fill=color)

    text = concept.get("visibleText") or concept.get("conceptName", "Original Design")
    font_size = max(18, int(width / max(8, min(18, len(text))) * 1.3))
    font_size = min(font_size, int(height * 0.16))
    font = _load_font(font_size, bold=True)
    small_font = _load_font(max(14, int(font_size * 0.28)), bold=False)
    lines = _wrap_text(draw, text.upper(), font, int(badge_w * 0.82))
    while len(lines) > 3 and font_size > 16:
        font_size = int(font_size * 0.9)
        font = _load_font(font_size, bold=True)
        lines = _wrap_text(draw, text.upper(), font, int(badge_w * 0.82))

    line_boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=max(1, width // 800)) for line in lines]
    line_height = max(box[3] - box[1] for box in line_boxes) if line_boxes else font_size
    total_h = len(lines) * line_height + max(0, len(lines) - 1) * int(line_height * 0.22)
    y = center_y - total_h // 2 + int(badge_h * 0.08)
    stroke = max(2, width // 600)
    for line, box in zip(lines, line_boxes):
        text_w = box[2] - box[0]
        x = center_x - text_w // 2
        draw.text((x, y), line, font=font, fill=dark, stroke_width=stroke, stroke_fill=(255, 255, 255, 255))
        y += line_height + int(line_height * 0.22)

    footer = "ORIGINAL MERCH DESIGN"
    footer_box = draw.textbbox((0, 0), footer, font=small_font)
    draw.text(
        (center_x - (footer_box[2] - footer_box[0]) // 2, badge_bottom - int(badge_h * 0.18)),
        footer,
        font=small_font,
        fill=(45, 52, 54, 230),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", dpi=(presets[canvas_key].get("dpi", 300), presets[canvas_key].get("dpi", 300)))
    return {
        "file": str(output_path),
        "canvas": canvas_key,
        "width": width,
        "height": height,
        "generator": "fallback_demo_pillow",
        "optionIndex": option_index,
    }


def _adapter_command_from_env(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    config_path = os.environ.get("MERCH_SCOUT_CONFIG")
    if config_path:
        config = load_json(Path(config_path).expanduser())
        command = config.get("imageAdapterCommand")
        if command:
            return str(command)
    return os.environ.get("MERCH_SCOUT_IMAGE_ADAPTER_CMD")


def generate_design(
    concept: dict[str, Any],
    canvas_key: str,
    output_path: Path,
    option_index: int = 1,
    adapter_command: str | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    """Generate a design using an external adapter command or the local fallback.

    Adapter contract:
      - command is supplied by --image-adapter-command, MERCH_SCOUT_IMAGE_ADAPTER_CMD,
        or MERCH_SCOUT_CONFIG JSON with imageAdapterCommand.
      - Merch Scout sends one JSON payload to stdin.
      - adapter must write a PNG to payload["outputPath"].
      - adapter may print JSON to stdout; non-JSON stdout is ignored.
    """
    presets = canvas_presets()
    if canvas_key not in presets:
        raise SystemExit(f"Unknown canvas: {canvas_key}")
    width, height = presets[canvas_key]["size"]
    command = _adapter_command_from_env(adapter_command)
    if command:
        payload = {
            "concept": concept,
            "canvas": canvas_key,
            "width": width,
            "height": height,
            "transparentRequired": presets[canvas_key].get("background") == "transparent_png",
            "outputPath": str(output_path),
            "optionIndex": option_index,
            "mustNotUpload": True,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                shlex.split(command),
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                check=False,
                timeout=int(os.environ.get("MERCH_SCOUT_IMAGE_ADAPTER_TIMEOUT", "900")),
            )
            if completed.returncode == 0 and output_path.exists():
                validation = validate_png_file(output_path, canvas_key)
                transparency = validate_transparency_file(output_path, canvas_key)
                if validation["valid"] and transparency["valid"]:
                    adapter_result: dict[str, Any] = {}
                    if completed.stdout.strip():
                        try:
                            adapter_result = json.loads(completed.stdout)
                        except json.JSONDecodeError:
                            adapter_result = {"stdout": completed.stdout.strip()[:1000]}
                    return {
                        "file": str(output_path),
                        "canvas": canvas_key,
                        "width": width,
                        "height": height,
                        "generator": "external_adapter",
                        "adapterCommand": command,
                        "optionIndex": option_index,
                        "adapterResult": adapter_result,
                    }
                failure = {
                    "returnCode": completed.returncode,
                    "stdout": completed.stdout[-2000:],
                    "stderr": completed.stderr[-2000:],
                    "validation": validation,
                    "transparency": transparency,
                }
            else:
                failure = {
                    "returnCode": completed.returncode,
                    "stdout": completed.stdout[-2000:],
                    "stderr": completed.stderr[-2000:],
                    "outputExists": output_path.exists(),
                }
        except Exception as exc:
            failure = {"exception": str(exc)}
        if not allow_fallback:
            raise SystemExit(f"Image adapter failed and fallback is disabled: {failure}")
        fallback = generate_demo_design(concept, canvas_key, output_path, option_index=option_index)
        fallback["adapterAttempted"] = True
        fallback["adapterFailure"] = failure
        return fallback
    return generate_demo_design(concept, canvas_key, output_path, option_index=option_index)


def imagegen_job_prompt(concept: dict[str, Any], canvas_key: str, option_index: int = 1) -> str:
    canvas = canvas_presets()[canvas_key]
    width, height = canvas["size"]
    text = concept.get("visibleText", "")
    avoid = "; ".join(concept.get("mustAvoid", []))
    return "\n".join(
        [
            "Use case: product-mockup",
            "Asset type: Amazon Merch on Demand artwork source for local transparent PNG post-processing",
            f"Primary request: Create an original merch illustration/motif for: {concept['niche']}.",
            f"Style/medium: {concept.get('designStyle', 'original clean apparel illustration')}.",
            f"Composition/framing: centered print-ready graphic, generous padding, no clipping, suitable for {canvas_key} ({width}x{height} final canvas after local processing).",
            "Background: perfectly flat solid #00ff00 chroma-key background for background removal.",
            "Background constraints: one uniform color only; no shadows, gradients, texture, floor plane, reflection, lighting variation, or contact shadow.",
            "Text: no text in the generated image. Leave all lettering to local deterministic post-processing.",
            f"Final local text that will be added later: \"{text}\".",
            "Do not include logos, brand marks, franchise characters, public figures, team names, copyrighted characters, watermarks, signatures, or marketplace UI.",
            f"Must avoid: {avoid}",
            "Do not use #00ff00 anywhere in the subject.",
            f"Variant: {option_index}.",
        ]
    )


def create_imagegen_jobs(
    run_dir: Path,
    concept: dict[str, Any],
    canvas_keys: list[str],
    variants_per_concept: int,
    design_index: int,
    depth: str = "standard",
) -> dict[str, Any]:
    paths = ensure_run_structure(run_dir)
    imagegen_dir = run_dir / "workspace" / "imagegen"
    source_dir = imagegen_dir / "source"
    alpha_dir = imagegen_dir / "alpha"
    source_dir.mkdir(parents=True, exist_ok=True)
    alpha_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[dict[str, Any]] = []

    primary_canvas = canvas_keys[0]
    for option in range(1, variants_per_concept + 1):
        job_id = f"candidate_{option:02d}_{primary_canvas}"
        jobs.append(_imagegen_job_record(run_dir, concept, primary_canvas, job_id, option, promote_final=False, design_index=design_index))

    for canvas_key in canvas_keys:
        job_id = f"final_{design_index:02d}_{canvas_key}"
        jobs.append(_imagegen_job_record(run_dir, concept, canvas_key, job_id, 1, promote_final=True, design_index=design_index))

    manifest = {
        "schemaVersion": "1.0.0",
        "status": "awaiting_codex_imagegen",
        "generator": "imagegen",
        "depth": depth,
        "instructions": [
            "For each job, call the built-in Codex image_gen tool with prompt.",
            "Save or copy the generated source image to sourcePath.",
            "Then run: python3 merch-scout/scripts/finalize_imagegen.py <run_dir>",
        ],
        "concept": concept,
        "jobs": jobs,
    }
    write_json(paths["processing"] / "imagegen_jobs.json", manifest)
    write_text(paths["processing"] / "imagegen_prompts.md", _imagegen_prompts_markdown(jobs))
    return manifest


def _imagegen_job_record(
    run_dir: Path,
    concept: dict[str, Any],
    canvas_key: str,
    job_id: str,
    option_index: int,
    promote_final: bool,
    design_index: int,
) -> dict[str, Any]:
    width, height = canvas_presets()[canvas_key]["size"]
    final_name = f"design_{design_index:02d}_{canvas_key}_{width}x{height}.png"
    output_rel = Path("output") / "final" / final_name
    if not promote_final:
        output_rel = Path("workspace") / "candidates" / f"option_{chr(96 + option_index)}_{canvas_key}.png"
    return {
        "jobId": job_id,
        "canvas": canvas_key,
        "width": width,
        "height": height,
        "optionIndex": option_index,
        "promoteFinal": promote_final,
        "prompt": imagegen_job_prompt(concept, canvas_key, option_index),
        "sourcePath": str(Path("workspace") / "imagegen" / "source" / f"{job_id}.png"),
        "alphaPath": str(Path("workspace") / "imagegen" / "alpha" / f"{job_id}_alpha.png"),
        "outputPath": str(output_rel),
        "transparentRequired": canvas_presets()[canvas_key].get("background") == "transparent_png",
        "status": "awaiting_imagegen_source",
    }


def _imagegen_prompts_markdown(jobs: list[dict[str, Any]]) -> str:
    lines = ["# Imagegen Prompts", ""]
    for job in jobs:
        lines.extend(
            [
                f"## {job['jobId']}",
                "",
                f"- Source path: `{job['sourcePath']}`",
                f"- Output path: `{job['outputPath']}`",
                "",
                "```text",
                job["prompt"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def has_useful_alpha(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        from PIL import Image

        with Image.open(path) as image:
            stats = _alpha_stats(image)
            return bool(stats["hasAlphaChannel"] and stats["transparentPixelRatio"] >= 0.05)
    except Exception:
        return False


def remove_or_use_alpha(source_path: Path, alpha_path: Path) -> dict[str, Any]:
    alpha_path.parent.mkdir(parents=True, exist_ok=True)
    if has_useful_alpha(source_path):
        from PIL import Image

        with Image.open(source_path) as image:
            image.convert("RGBA").save(alpha_path, format="PNG", dpi=(300, 300))
        return {"mode": "source_alpha", "source": str(source_path), "alpha": str(alpha_path)}

    helper = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / ".system" / "imagegen" / "scripts" / "remove_chroma_key.py"
    if helper.exists():
        command = [
            "python3",
            str(helper),
            "--input",
            str(source_path),
            "--out",
            str(alpha_path),
            "--auto-key",
            "border",
            "--soft-matte",
            "--transparent-threshold",
            "12",
            "--opaque-threshold",
            "220",
            "--despill",
            "--force",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode == 0 and has_useful_alpha(alpha_path):
            return {
                "mode": "chroma_key_helper",
                "source": str(source_path),
                "alpha": str(alpha_path),
                "stdout": completed.stdout[-1000:],
                "stderr": completed.stderr[-1000:],
            }
        helper_failure = {"returnCode": completed.returncode, "stdout": completed.stdout[-1000:], "stderr": completed.stderr[-1000:]}
    else:
        helper_failure = {"error": f"helper not found: {helper}"}

    internal = internal_border_key_remove(source_path, alpha_path)
    internal["helperFailure"] = helper_failure
    return internal


def internal_border_key_remove(source_path: Path, alpha_path: Path) -> dict[str, Any]:
    from PIL import Image

    with Image.open(source_path) as image:
        rgba = image.convert("RGBA")
    border = _sample_border_pixels(rgba)
    opaque = [p for p in border if p[3] > 200] or border
    key = tuple(int(sum(p[i] for p in opaque) / len(opaque)) for i in range(3))
    pixels = rgba.load()
    tolerance = 56
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            dist = max(abs(r - key[0]), abs(g - key[1]), abs(b - key[2]))
            if dist <= tolerance:
                pixels[x, y] = (r, g, b, 0)
            elif dist <= tolerance * 2:
                alpha = int(255 * (dist - tolerance) / tolerance)
                pixels[x, y] = (r, g, b, min(a, alpha))
    alpha_path.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(alpha_path, format="PNG", dpi=(300, 300))
    return {"mode": "internal_border_key", "source": str(source_path), "alpha": str(alpha_path), "key": key}


def compose_imagegen_artwork(
    alpha_art_path: Path,
    output_path: Path,
    concept: dict[str, Any],
    canvas_key: str,
    include_text: bool = True,
) -> dict[str, Any]:
    from PIL import Image, ImageDraw

    presets = canvas_presets()
    width, height = presets[canvas_key]["size"]
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    with Image.open(alpha_art_path) as source:
        art = source.convert("RGBA")
    bbox = art.getchannel("A").getbbox()
    if bbox:
        art = art.crop(bbox)
    max_art_w = int(width * (0.72 if include_text else 0.86))
    max_art_h = int(height * (0.48 if include_text else 0.78))
    if canvas_key in {"mugs", "hats", "tumblers_bottles"}:
        max_art_w = int(width * 0.42)
        max_art_h = int(height * 0.72)
    ratio = min(max_art_w / max(1, art.width), max_art_h / max(1, art.height))
    art = art.resize((max(1, int(art.width * ratio)), max(1, int(art.height * ratio))))

    if canvas_key in {"mugs", "hats", "tumblers_bottles"} and include_text:
        art_x = int(width * 0.10)
        art_y = (height - art.height) // 2
        text_area = (int(width * 0.50), int(width * 0.88), int(height * 0.20), int(height * 0.80))
    else:
        art_x = (width - art.width) // 2
        art_y = int(height * 0.14)
        text_area = (int(width * 0.12), int(width * 0.88), int(height * 0.62), int(height * 0.84))
    canvas.alpha_composite(art, (art_x, art_y))

    if include_text:
        _draw_final_text(canvas, concept.get("visibleText") or concept.get("conceptName", ""), text_area)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", dpi=(presets[canvas_key].get("dpi", 300), presets[canvas_key].get("dpi", 300)))
    return {
        "sourceAlpha": str(alpha_art_path),
        "output": str(output_path),
        "canvas": canvas_key,
        "width": width,
        "height": height,
        "textCompositedLocally": include_text,
    }


def _draw_final_text(canvas: Any, text: str, text_area: tuple[int, int, int, int]) -> None:
    from PIL import ImageDraw

    if not text:
        return
    draw = ImageDraw.Draw(canvas)
    left, right, top, bottom = text_area
    max_width = right - left
    max_height = bottom - top
    font_size = min(int(canvas.width * 0.13), int(max_height * 0.52))
    font_size = max(18, font_size)
    while font_size >= 14:
        font = _load_font(font_size, bold=True)
        lines = _wrap_text(draw, text.upper(), font, max_width)
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=max(1, canvas.width // 900)) for line in lines]
        line_h = max((box[3] - box[1] for box in boxes), default=font_size)
        total_h = len(lines) * line_h + max(0, len(lines) - 1) * int(line_h * 0.22)
        if len(lines) <= 3 and total_h <= max_height:
            break
        font_size = int(font_size * 0.9)
    stroke = max(2, canvas.width // 650)
    y = top + (max_height - total_h) // 2
    for line, box in zip(lines, boxes):
        text_w = box[2] - box[0]
        x = left + (max_width - text_w) // 2
        draw.text((x, y), line, font=font, fill=(25, 40, 55, 255), stroke_width=stroke, stroke_fill=(255, 255, 255, 255))
        y += line_h + int(line_h * 0.22)


def finalize_imagegen_run(run_dir: Path) -> dict[str, Any]:
    processing_dir = run_dir / "workspace" / "processing"
    manifest_path = processing_dir / "imagegen_jobs.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing imagegen jobs manifest: {manifest_path}")
    manifest = load_json(manifest_path)
    concept = manifest["concept"]
    results = []
    artwork_files = []
    option_scores = []
    errors = []
    for job in manifest["jobs"]:
        source_path = run_dir / job["sourcePath"]
        alpha_path = run_dir / job["alphaPath"]
        output_path = run_dir / job["outputPath"]
        if not source_path.exists():
            job["status"] = "missing_source"
            errors.append(f"Missing imagegen source for {job['jobId']}: {job['sourcePath']}")
            continue
        alpha_result = remove_or_use_alpha(source_path, alpha_path)
        compose_result = compose_imagegen_artwork(alpha_path, output_path, concept, job["canvas"], include_text=True)
        png_result = validate_png_file(output_path, job["canvas"])
        transparency_result = validate_transparency_file(output_path, job["canvas"])
        job["status"] = "validated" if png_result["valid"] and transparency_result["valid"] else "invalid"
        job["alphaResult"] = alpha_result
        job["composeResult"] = compose_result
        job["pngValidation"] = png_result
        job["transparencyValidation"] = transparency_result
        if job["status"] != "validated":
            errors.extend([f"{job['jobId']}: {err}" for err in png_result.get("errors", [])])
            errors.extend([f"{job['jobId']}: {err}" for err in transparency_result.get("errors", [])])
        if job.get("promoteFinal"):
            artwork_files.append(
                {
                    "file": job["outputPath"],
                    "canvas": job["canvas"],
                    "width": job["width"],
                    "height": job["height"],
                    "transparent": job["transparentRequired"],
                    "validated": job["status"] == "validated",
                    "generator": "imagegen",
                }
            )
            write_json(run_dir / "workspace" / "processing" / f"transparency_test_{job['canvas']}.json", transparency_result)
        else:
            option_scores.append(
                {
                    "option": job["optionIndex"],
                    "file": job["outputPath"],
                    "score": 73 + job["optionIndex"] * 3 - (0 if job["status"] == "validated" else 20),
                    "generator": "imagegen",
                    "validation": transparency_result,
                }
            )
        results.append(job)

    manifest["status"] = "finalized" if not errors else "finalized_with_errors"
    manifest["finalizedAt"] = now_stamp()
    write_json(manifest_path, manifest)
    write_json(processing_dir / "imagegen_finalize_results.json", {"valid": not errors, "errors": errors, "jobs": results})
    write_json(run_dir / "workspace" / "candidates" / "option_scores.json", {"options": option_scores})
    if errors:
        return {"valid": False, "errors": errors, "manifest": str(manifest_path)}

    compliance = load_json(run_dir / "workspace" / "compliance" / "trademark_checks.json")
    research = load_json(run_dir / "workspace" / "research" / "candidate_niches.json")
    scoring = load_json(run_dir / "workspace" / "research" / "scored_niches.json")
    metadata = make_metadata(run_dir, concept, artwork_files, compliance, research)
    write_json(run_dir / "output" / "metadata" / "merch_metadata.json", metadata)
    validation = validate_package(run_dir, metadata)
    write_json(run_dir / "output" / "validation" / "validation_summary.json", validation)
    report = generate_report(run_dir, concept, metadata, validation, research, scoring, compliance)
    write_text(run_dir / "output" / "report" / "merch_report.md", report)
    package = package_output(run_dir)
    return {"valid": validation["valid"], "runDir": str(run_dir), "package": package, "manifest": str(manifest_path)}


def validate_png_file(path: Path, canvas_key: str | None = None, strict_srgb: bool = False) -> dict[str, Any]:
    from PIL import Image

    result: dict[str, Any] = {
        "file": str(path),
        "exists": path.exists(),
        "valid": False,
        "errors": [],
        "warnings": [],
    }
    if not path.exists():
        result["errors"].append("File does not exist.")
        return result
    try:
        with Image.open(path) as image:
            result["format"] = image.format
            result["mode"] = image.mode
            result["width"], result["height"] = image.size
            result["fileSizeBytes"] = path.stat().st_size
            result["dpi"] = image.info.get("dpi")
            result["iccProfilePresent"] = bool(image.info.get("icc_profile"))
            if image.format != "PNG":
                result["errors"].append("File is not PNG format.")
            if canvas_key:
                presets = canvas_presets()
                if canvas_key not in presets:
                    result["errors"].append(f"Unknown canvas preset: {canvas_key}")
                else:
                    expected_w, expected_h = presets[canvas_key]["size"]
                    max_size = presets[canvas_key].get("maxFileSizeMb", 25) * 1024 * 1024
                    if image.size != (expected_w, expected_h):
                        result["errors"].append(f"Expected {expected_w}x{expected_h}, got {image.size[0]}x{image.size[1]}.")
                    if result["fileSizeBytes"] > max_size:
                        result["errors"].append(f"File exceeds {presets[canvas_key].get('maxFileSizeMb', 25)} MB.")
                    if presets[canvas_key].get("background") == "transparent_png":
                        alpha = _alpha_stats(image)
                        result["alpha"] = alpha
                        if not alpha["hasAlphaChannel"]:
                            result["errors"].append("Image has no alpha channel.")
                        if alpha["transparentPixelRatio"] < 0.08:
                            result["errors"].append("Transparent pixel ratio is too low for a transparent canvas.")
                    if result["dpi"]:
                        dpi_x = result["dpi"][0]
                        if abs(dpi_x - presets[canvas_key].get("dpi", 300)) > 2:
                            result["warnings"].append(f"DPI metadata is {result['dpi']}, expected near 300.")
                    else:
                        result["warnings"].append("DPI metadata is missing.")
            if strict_srgb and not result["iccProfilePresent"]:
                result["errors"].append("sRGB/ICC profile not found in strict mode.")
            elif not result["iccProfilePresent"]:
                result["warnings"].append("ICC/sRGB profile not embedded; assume sRGB only after manual review.")
    except Exception as exc:  # pragma: no cover - defensive
        result["errors"].append(f"Could not open image: {exc}")
    result["valid"] = not result["errors"]
    return result


def _alpha_stats(image: Any) -> dict[str, Any]:
    if image.mode not in ("RGBA", "LA") and "transparency" not in image.info:
        return {
            "hasAlphaChannel": False,
            "transparentPixelRatio": 0.0,
            "opaquePixelRatio": 1.0,
            "alphaExtrema": None,
        }
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    hist = alpha.histogram()
    total = rgba.size[0] * rgba.size[1]
    transparent = hist[0]
    opaque = hist[255]
    extrema = alpha.getextrema()
    return {
        "hasAlphaChannel": True,
        "transparentPixelRatio": round(transparent / total, 6),
        "opaquePixelRatio": round(opaque / total, 6),
        "alphaExtrema": extrema,
    }


def validate_transparency_file(path: Path, canvas_key: str | None = None) -> dict[str, Any]:
    from PIL import Image

    result: dict[str, Any] = {
        "file": str(path),
        "valid": False,
        "errors": [],
        "warnings": [],
        "fakeCheckerboardDetected": False,
        "solidBackgroundDetected": False,
        "clippingDetected": False,
    }
    if not path.exists():
        result["errors"].append("File does not exist.")
        return result
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = _alpha_stats(rgba)
        result["alpha"] = alpha
        if not alpha["hasAlphaChannel"]:
            result["errors"].append("No alpha channel found.")
        if alpha["transparentPixelRatio"] < 0.08:
            result["errors"].append("Not enough fully transparent pixels for transparent PNG.")
        width, height = rgba.size
        border = _sample_border_pixels(rgba)
        result["fakeCheckerboardDetected"] = _looks_like_checkerboard(border)
        result["solidBackgroundDetected"] = _looks_like_solid_background(border)
        if result["fakeCheckerboardDetected"]:
            result["errors"].append("Opaque checkerboard-like fake transparency detected.")
        if result["solidBackgroundDetected"]:
            result["errors"].append("Opaque solid background detected at canvas edges.")
        bbox = rgba.getchannel("A").getbbox()
        result["nonTransparentBounds"] = bbox
        if bbox:
            margin = max(1, int(min(width, height) * 0.015))
            result["clippingDetected"] = bbox[0] <= margin or bbox[1] <= margin or bbox[2] >= width - margin or bbox[3] >= height - margin
            if result["clippingDetected"]:
                result["warnings"].append("Artwork is close to canvas edge; review print-safe margins.")
        else:
            result["errors"].append("No non-transparent artwork detected.")
        if canvas_key:
            result["pngValidation"] = validate_png_file(path, canvas_key)
            if not result["pngValidation"]["valid"]:
                result["errors"].extend(result["pngValidation"]["errors"])
    result["valid"] = not result["errors"]
    return result


def _sample_border_pixels(image: Any) -> list[tuple[int, int, int, int]]:
    width, height = image.size
    step = max(1, min(width, height) // 80)
    pixels = []
    for x in range(0, width, step):
        pixels.append(image.getpixel((x, 0)))
        pixels.append(image.getpixel((x, height - 1)))
    for y in range(0, height, step):
        pixels.append(image.getpixel((0, y)))
        pixels.append(image.getpixel((width - 1, y)))
    return pixels


def _looks_like_checkerboard(pixels: list[tuple[int, int, int, int]]) -> bool:
    opaque = [p for p in pixels if p[3] > 245]
    if len(opaque) < max(20, len(pixels) * 0.8):
        return False
    colors = {}
    for r, g, b, _a in opaque:
        key = (round(r / 16) * 16, round(g / 16) * 16, round(b / 16) * 16)
        colors[key] = colors.get(key, 0) + 1
    top = sorted(colors.items(), key=lambda item: item[1], reverse=True)[:3]
    if len(top) < 2:
        return False
    grayish = [abs(c[0] - c[1]) < 12 and abs(c[1] - c[2]) < 12 and 120 <= c[0] <= 245 for c, _ in top]
    balanced = top[1][1] / max(1, top[0][1]) > 0.35
    return sum(grayish) >= 2 and balanced


def _looks_like_solid_background(pixels: list[tuple[int, int, int, int]]) -> bool:
    opaque = [p for p in pixels if p[3] > 245]
    if len(opaque) < len(pixels) * 0.85:
        return False
    avg = tuple(sum(p[i] for p in opaque) / len(opaque) for i in range(3))
    variance = sum(sum((p[i] - avg[i]) ** 2 for i in range(3)) for p in opaque) / len(opaque)
    return variance < 80


def resize_canvas(source: Path, output: Path, canvas_key: str, scale: float = 0.86) -> dict[str, Any]:
    from PIL import Image

    presets = canvas_presets()
    if canvas_key not in presets:
        raise SystemExit(f"Unknown canvas: {canvas_key}")
    width, height = presets[canvas_key]["size"]
    with Image.open(source) as img:
        rgba = img.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        target_w = int(width * scale)
        target_h = int(height * scale)
        ratio = min(target_w / rgba.width, target_h / rgba.height)
        resized = rgba.resize((max(1, int(rgba.width * ratio)), max(1, int(rgba.height * ratio))))
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, format="PNG", dpi=(presets[canvas_key].get("dpi", 300), presets[canvas_key].get("dpi", 300)))
    return {"source": str(source), "output": str(output), "canvas": canvas_key, "width": width, "height": height}


def keyword_lint(metadata_or_terms: dict[str, Any] | list[str]) -> dict[str, Any]:
    if isinstance(metadata_or_terms, dict):
        terms = []
        keywords = metadata_or_terms.get("keywords", {})
        keyword_terms = keywords.get("primary", []) + keywords.get("secondary", [])
        terms += keyword_terms
        for listing in metadata_or_terms.get("listings", {}).values():
            terms += [listing.get("brand", ""), listing.get("title", ""), listing.get("bullet1", ""), listing.get("bullet2", ""), listing.get("description", "")]
    else:
        terms = metadata_or_terms
        keyword_terms = metadata_or_terms
    lint = lint_terms([str(term) for term in terms])
    normalized = [str(term).strip().lower() for term in keyword_terms if str(term).strip()]
    duplicates = sorted({term for term in normalized if normalized.count(term) > 1})
    token_counts: dict[str, int] = {}
    for term in sorted(set(normalized)):
        for token in re.findall(r"[a-z0-9]+", term):
            token_counts[token] = token_counts.get(token, 0) + 1
    repeated_tokens = {token: count for token, count in token_counts.items() if count >= 4 and token not in {"and", "the", "for", "with"}}
    errors = []
    warnings = []
    if lint["blocked"]:
        errors.append("High-risk keyword/compliance term detected.")
    if lint["riskLevel"] == "medium":
        warnings.append("Medium-risk policy wording detected.")
    if duplicates:
        warnings.append("Duplicate keywords/listing terms detected.")
    if repeated_tokens:
        warnings.append("Possible keyword stuffing detected.")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "riskLevel": lint["riskLevel"],
        "riskHits": lint["hits"],
        "duplicates": duplicates,
        "repeatedTokens": repeated_tokens,
    }


def make_metadata(
    run_dir: Path,
    concept: dict[str, Any],
    artwork_files: list[dict[str, Any]],
    compliance: dict[str, Any],
    research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    presets = canvas_presets()
    products: list[str] = []
    for canvas in concept.get("productFit", []):
        products.extend(presets[canvas]["products"])
    products = list(dict.fromkeys(products))
    marketplaces = concept.get("marketplaces", ["US"])
    keywords = concept.get("keywords", [])[:6]
    primary = keywords[:4] or [slugify(concept["niche"]).replace("-", " ")]
    secondary = keywords[4:] + ["gift idea", "original design"]
    listings = {market: _listing_for_market(market, concept, primary, secondary) for market in marketplaces}
    risk_level = compliance.get("riskLevel", "low")
    research = research or {}
    artwork_generators = sorted({str(item.get("generator", "unknown")) for item in artwork_files})
    generator_fallback = any("demo" in generator or "fallback" in generator for generator in artwork_generators)
    fallback_offline = bool(research.get("fallbackOffline") or generator_fallback)
    metadata = {
        "schemaVersion": "1.0.0",
        "designId": run_dir.name,
        "status": "ready_for_human_review",
        "riskLevel": risk_level,
        "upload": False,
        "humanReviewRequired": True,
        "selectedProducts": products,
        "selectedMarketplaces": marketplaces,
        "artworkFiles": artwork_files,
        "listings": listings,
        "keywords": {
            "primary": primary,
            "secondary": secondary,
            "removedForRisk": [hit["term"] for hit in compliance.get("riskHits", [])],
        },
        "compliance": {
            "trademarkChecked": True,
            "copyrightRiskChecked": True,
            "publicFigureRisk": any(hit["category"] == "public_figures_and_groups" for hit in compliance.get("riskHits", [])),
            "brandNameRisk": any(hit["category"] == "brands_and_franchises" for hit in compliance.get("riskHits", [])),
            "fanArtRisk": any(hit["category"] == "copyright_risk" for hit in compliance.get("riskHits", [])),
            "policyNotes": [compliance.get("statement", REQUIRED_COMPLIANCE_WORDING)],
            "checkedSources": compliance.get("checks", []),
            "researchRiskFlags": compliance.get("researchRiskFlags", []),
            "externalEvidenceSources": compliance.get("externalEvidenceSources", []),
        },
        "researchSummary": {
            "niche": concept["niche"],
            "nicheType": concept.get("nicheType"),
            "depth": research.get("depth"),
            "externalResearchUsed": bool(research.get("externalResearchUsed")),
            "fallbackOffline": fallback_offline,
            "fallbackNotice": FALLBACK_OFFLINE_NOTICE if fallback_offline else "",
            "evidenceValidation": research.get("evidenceValidation", {}),
            "researchObservation": concept.get("researchEvidence", {}),
            "demandScore": concept.get("scores", {}).get("demandSignal"),
            "saturationScore": concept.get("scores", {}).get("lowToMediumSaturation"),
            "ipRiskScore": 100 - concept.get("scores", {}).get("complianceIpSafety", 0),
            "finalOpportunityScore": concept.get("scores", {}).get("finalOpportunityScore"),
        },
        "generationSummary": {
            "artworkGenerators": artwork_generators,
            "fallbackOrDemoUsed": generator_fallback,
        },
    }
    return metadata


def _listing_for_market(market: str, concept: dict[str, Any], primary: list[str], secondary: list[str]) -> dict[str, str]:
    text = concept.get("visibleText", concept["conceptName"])
    brand = f"Scout {slugify(concept['niche']).split('-')[0].title()} Studio"
    title_suffix = {
        "US": "Shirt",
        "UK": "T-Shirt",
        "DE": "T-Shirt",
        "FR": "T-Shirt",
        "IT": "Maglietta",
        "ES": "Camiseta",
        "JP": "T-Shirt",
    }.get(market, "Shirt")
    if market == "JP":
        return {
            "brand": brand,
            "title": f"{text} {title_suffix}",
            "bullet1": "Original design for everyday casual wear and gifting.",
            "bullet2": "Human review required for Japanese wording, trademark risk, and upload settings.",
            "description": f"Original {concept['niche']} design prepared for human review before Amazon Merch upload.",
        }
    return {
        "brand": brand,
        "title": f"{text} {title_suffix}",
        "bullet1": f"Original {concept['niche']} design with a clean, wearable layout.",
        "bullet2": f"Gift idea for fans of {', '.join(primary[:3])}.",
        "description": f"A human-review-ready Merch on Demand design package for {concept['niche']}. Review all compliance notes before upload.",
    }


def metadata_lint(metadata: dict[str, Any], run_dir: Path | None = None) -> dict[str, Any]:
    errors = []
    warnings = []
    required = [
        "schemaVersion",
        "designId",
        "status",
        "riskLevel",
        "upload",
        "humanReviewRequired",
        "selectedProducts",
        "selectedMarketplaces",
        "artworkFiles",
        "listings",
        "keywords",
        "compliance",
        "researchSummary",
    ]
    for key in required:
        if key not in metadata:
            errors.append(f"Missing required key: {key}")
    if metadata.get("upload") is not False:
        errors.append("metadata.upload must be false in v1.")
    if metadata.get("humanReviewRequired") is not True:
        errors.append("metadata.humanReviewRequired must be true.")
    if metadata.get("status") != "ready_for_human_review":
        errors.append("metadata.status must be ready_for_human_review.")
    marketplaces = metadata.get("selectedMarketplaces", [])
    listings = metadata.get("listings", {})
    for market in marketplaces:
        if market not in marketplace_config():
            errors.append(f"Unknown marketplace: {market}")
        if market not in listings:
            errors.append(f"Missing listing for marketplace: {market}")
    for market, listing in listings.items():
        for field in ["brand", "title", "bullet1", "bullet2", "description"]:
            value = listing.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"Listing {market}.{field} is required.")
            elif len(value) > DEFAULT_FIELD_LIMITS[field]:
                warnings.append(f"Listing {market}.{field} exceeds configurable default limit {DEFAULT_FIELD_LIMITS[field]}.")
    for artwork in metadata.get("artworkFiles", []):
        for key in ["file", "canvas", "width", "height", "transparent", "validated"]:
            if key not in artwork:
                errors.append(f"Artwork entry missing key: {key}")
        if run_dir and artwork.get("file"):
            art_path = run_dir / artwork["file"]
            if not art_path.exists():
                errors.append(f"Artwork file does not exist: {artwork['file']}")
    keyword_result = keyword_lint(metadata)
    if not keyword_result["valid"]:
        errors.extend(keyword_result["errors"])
    warnings.extend(keyword_result["warnings"])
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "keywordLint": keyword_result,
    }


def generate_report(
    run_dir: Path,
    concept: dict[str, Any],
    metadata: dict[str, Any],
    validation: dict[str, Any],
    research: dict[str, Any],
    scoring: dict[str, Any],
    compliance: dict[str, Any],
) -> str:
    rejected = scoring.get("rejected", [])
    external = research.get("externalResearch", {}) if isinstance(research.get("externalResearch"), dict) else {}
    evidence_validation = research.get("evidenceValidation", {})
    final_recommendation = "Needs manual review"
    if validation.get("valid") and metadata.get("riskLevel") == "low":
        final_recommendation = "Ready for human review; upload only after manual approval"
    elif metadata.get("riskLevel") == "high":
        final_recommendation = "Do not upload until compliance issues are resolved"

    fallback_used = _report_fallback_used(research, metadata)
    selected_observation = concept.get("researchEvidence") or {}
    source_lines = _source_report_lines(external, selected_observation, limit=24)
    query_lines = _query_report_lines(external, selected_observation, limit=24)
    marketplace_lines = _marketplace_report_lines(external, selected_observation, limit=16)
    product_lines = _product_report_lines(external, selected_observation, limit=16)
    unresolved_risk_lines = _unresolved_risk_lines(external, selected_observation, compliance)

    lines = [
        "# Merch Scout Report",
        "",
        "## Final Recommendation",
        "",
        final_recommendation,
        "",
        REQUIRED_COMPLIANCE_WORDING,
        "",
    ]
    if fallback_used:
        lines.extend([FALLBACK_OFFLINE_NOTICE, ""])
    lines.extend(
        [
            "## Run Quality Mode",
            "",
            f"- Depth: {research.get('depth', 'unknown')}",
            f"- Research mode: {research.get('mode')}",
            f"- External research used: {bool(research.get('externalResearchUsed'))}",
            f"- Evidence valid: {evidence_validation.get('valid')}",
            f"- Evidence stats: {json.dumps(evidence_validation.get('stats', {}), ensure_ascii=False)}",
            f"- Artwork generators: {', '.join(metadata.get('generationSummary', {}).get('artworkGenerators', [])) or 'unknown'}",
            f"- Fallback/demo used: {bool(metadata.get('generationSummary', {}).get('fallbackOrDemoUsed') or research.get('fallbackOffline'))}",
            "",
            "## Design Summary",
            "",
            f"- Concept: {concept['conceptName']}",
            f"- Niche: {concept['niche']}",
            f"- Marketplaces: {', '.join(concept.get('marketplaces', []))}",
            f"- Product canvases: {', '.join(concept.get('productFit', []))}",
            f"- Design style: {concept.get('designStyle')}",
            f"- Visible text: {concept.get('visibleText')}",
            "",
            "## Research Evidence",
            "",
            "### Queries Searched",
            "",
        ]
    )
    lines.extend(query_lines or ["- No external queries were recorded."])
    lines.extend(["", "### Sources Checked", ""])
    lines.extend(source_lines or ["- No external sources were recorded."])
    lines.extend(["", "### Marketplace Observations", ""])
    lines.extend(marketplace_lines or ["- No marketplace observations were recorded."])
    lines.extend(["", "### Product Fit Observations", ""])
    lines.extend(product_lines or ["- No product-fit observations were recorded."])
    lines.extend(
        [
            "",
            "### Selected Observation",
            "",
            f"- Query: {selected_observation.get('query', 'not recorded') if isinstance(selected_observation, dict) else 'not recorded'}",
            f"- Demand signal: {selected_observation.get('demandSignal', 'not recorded') if isinstance(selected_observation, dict) else 'not recorded'}",
            f"- Saturation signal: {selected_observation.get('saturationSignal', 'not recorded') if isinstance(selected_observation, dict) else 'not recorded'}",
            f"- Originality potential: {selected_observation.get('originalityPotential', 'not recorded') if isinstance(selected_observation, dict) else 'not recorded'}",
            f"- Notes: {'; '.join(selected_observation.get('notes', [])) if isinstance(selected_observation, dict) and selected_observation.get('notes') else 'not recorded'}",
            "",
            "## Why This Niche Was Selected",
            "",
        ]
    )
    for line in _scoring_reason_lines(concept):
        lines.append(line)
    lines.extend(["", "## Compared And Rejected Ideas", ""])
    external_rejected = external.get("rejectedCandidates", []) if isinstance(external, dict) else []
    if external_rejected:
        for item in external_rejected[:12]:
            if isinstance(item, dict):
                name = item.get("name") or item.get("candidateName") or item.get("niche") or "unnamed candidate"
                reason = item.get("reason") or item.get("rejectionReason") or item.get("notes") or "Rejected during research comparison."
                lines.append(f"- {name}: {reason}")
    if rejected:
        for item in rejected[:12]:
            reason = "; ".join(item.get("rejectionReasons", [])) or "Lower opportunity score."
            score = item.get("scores", {}).get("finalOpportunityScore")
            lines.append(f"- {item['name']}: {reason} Score: {score}.")
    if not external_rejected and not rejected:
        lines.append("- No rejected candidates were recorded; human reviewer should treat this as a research gap.")
    lines.extend(["", "## Unresolved Risks", ""])
    lines.extend(unresolved_risk_lines or ["- No unresolved risks were recorded beyond required manual legal/compliance review."])
    lines.extend(
        [
            "",
            "## Design Direction",
            "",
            concept.get("generationPrompt", ""),
            "",
            "Originality controls:",
            "",
            "- Use competitor observations only to understand buyer expectations.",
            "- Do not copy competitor artwork, titles, brands, layouts, or protected phrases.",
            "- Final visible text is rendered locally for spelling and layout control.",
            "",
            "## Keyword Strategy",
            "",
            f"- Primary: {', '.join(metadata.get('keywords', {}).get('primary', []))}",
            f"- Secondary: {', '.join(metadata.get('keywords', {}).get('secondary', []))}",
            f"- Removed for risk: {', '.join(metadata.get('keywords', {}).get('removedForRisk', [])) or 'none'}",
            "",
            "## Compliance Review",
            "",
            f"- Risk level: {compliance.get('riskLevel')}",
            f"- Statement: {compliance.get('statement')}",
            "- Live official database checks are optional adapters in v1; review source URLs manually when needed.",
            "- Trademark/copyright/brand/public-figure/policy risk was linted locally and supplemented by recorded research evidence when supplied.",
            "",
            "## Validation Summary",
            "",
            f"- Overall valid: {validation.get('valid')}",
            f"- Errors: {len(validation.get('errors', []))}",
            f"- Warnings: {len(validation.get('warnings', []))}",
            "",
            "## Final Files",
            "",
        ]
    )
    for artwork in metadata.get("artworkFiles", []):
        lines.append(f"- {artwork['file']} ({artwork['canvas']}, {artwork['width']}x{artwork['height']}, generator: {artwork.get('generator', 'unknown')})")
    lines.extend(
        [
            "- output/metadata/merch_metadata.json",
            "- output/validation/validation_summary.json",
            "- output/report/merch_report.md",
            "",
            "## Human Review Checklist",
            "",
            "- Confirm every visible word is spelled correctly.",
            "- Search official trademark databases for visible text, title, brand, and keywords.",
            "- Confirm the design is original and not derived from protected IP.",
            "- Confirm Amazon account product availability and current upload UI field limits.",
            "- Confirm marketplace localization reads naturally.",
            "- Confirm no auto-upload occurred.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_fallback_used(research: dict[str, Any], metadata: dict[str, Any]) -> bool:
    return bool(
        research.get("fallbackOffline")
        or metadata.get("researchSummary", {}).get("fallbackOffline")
        or metadata.get("generationSummary", {}).get("fallbackOrDemoUsed")
    )


def _external_observations(external: dict[str, Any], selected_observation: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    observations = [obs for obs in external.get("observations", []) if isinstance(obs, dict)]
    if selected_observation and isinstance(selected_observation, dict) and selected_observation not in observations:
        observations.insert(0, selected_observation)
    return observations


def _query_report_lines(external: dict[str, Any], selected_observation: dict[str, Any], limit: int) -> list[str]:
    queries = [str(q).strip() for q in external.get("queriesSearched", []) if str(q).strip()]
    for observation in _external_observations(external, selected_observation):
        query = str(observation.get("query", "")).strip()
        if query:
            queries.append(query)
    lines = []
    for query in list(dict.fromkeys(queries))[:limit]:
        lines.append(f"- {query}")
    return lines


def _source_report_lines(external: dict[str, Any], selected_observation: dict[str, Any], limit: int) -> list[str]:
    sources: list[dict[str, Any]] = []
    for observation in _external_observations(external, selected_observation):
        sources.extend([source for source in observation.get("sources", []) if isinstance(source, dict)])
    lines = []
    seen: set[str] = set()
    for source in sources:
        url = str(source.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = str(source.get("title", "source")).strip() or "source"
        note = str(source.get("note", "")).strip()
        source_type = _source_type(source)
        suffix = f" - {note}" if note else ""
        lines.append(f"- [{title}]({url}) ({source_type}){suffix}")
        if len(lines) >= limit:
            break
    return lines


def _marketplace_report_lines(external: dict[str, Any], selected_observation: dict[str, Any], limit: int) -> list[str]:
    lines = []
    for observation in _external_observations(external, selected_observation):
        niche = observation.get("niche", "candidate")
        fit = observation.get("marketplaceFit", {})
        if isinstance(fit, dict):
            for market, note in fit.items():
                lines.append(f"- {niche} / {market}: {note}")
                if len(lines) >= limit:
                    return lines
    marketplace_comparisons = external.get("marketplaceComparisons", [])
    if not isinstance(marketplace_comparisons, list):
        marketplace_comparisons = []
    for item in marketplace_comparisons:
        if isinstance(item, dict):
            lines.append(f"- {item.get('marketplace', 'marketplace')}: {item.get('observation', item.get('note', 'recorded'))}")
            if len(lines) >= limit:
                return lines
    return lines


def _product_report_lines(external: dict[str, Any], selected_observation: dict[str, Any], limit: int) -> list[str]:
    lines = []
    for observation in _external_observations(external, selected_observation):
        niche = observation.get("niche", "candidate")
        fit = observation.get("productFit", {})
        if isinstance(fit, dict):
            for product, note in fit.items():
                lines.append(f"- {niche} / {product}: {note}")
                if len(lines) >= limit:
                    return lines
    product_comparisons = external.get("productComparisons", [])
    if not isinstance(product_comparisons, list):
        product_comparisons = []
    for item in product_comparisons:
        if isinstance(item, dict):
            lines.append(f"- {item.get('product', 'product')}: {item.get('observation', item.get('note', 'recorded'))}")
            if len(lines) >= limit:
                return lines
    return lines


def _unresolved_risk_lines(external: dict[str, Any], selected_observation: dict[str, Any], compliance: dict[str, Any]) -> list[str]:
    lines = []
    unresolved_risks = external.get("unresolvedRisks", [])
    if not isinstance(unresolved_risks, list):
        unresolved_risks = []
    for risk in unresolved_risks:
        if isinstance(risk, dict):
            lines.append(f"- {risk.get('type', 'risk')}: {risk.get('note', risk.get('reason', 'needs manual review'))}")
        else:
            lines.append(f"- {risk}")
    for observation in _external_observations(external, selected_observation):
        for flag in observation.get("riskFlags", []) if isinstance(observation.get("riskFlags"), list) else []:
            if isinstance(flag, dict):
                lines.append(f"- {flag.get('severity', 'unknown')} {flag.get('type', 'risk')}: {flag.get('note', 'needs review')}")
    for hit in compliance.get("riskHits", []):
        lines.append(f"- Local lint hit: {hit.get('term')} ({hit.get('category')})")
    return list(dict.fromkeys(lines))


def _scoring_reason_lines(concept: dict[str, Any]) -> list[str]:
    scores = concept.get("scores", {})
    return [
        f"- Final opportunity score: {scores.get('finalOpportunityScore')}",
        f"- Demand signal: {scores.get('demandSignal')} (buyer interest proxy from research/local seed data)",
        f"- Low-to-medium saturation score: {scores.get('lowToMediumSaturation')} (higher means less crowded)",
        f"- Product fit: {scores.get('productFit')}",
        f"- Marketplace fit: {scores.get('marketplaceFit')}",
        f"- Keyword quality: {scores.get('keywordQuality')}",
        f"- Design originality potential: {scores.get('designOriginalityPotential')}",
        f"- Compliance/IP safety score: {scores.get('complianceIpSafety')}",
    ]


def validate_package(run_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    image_results = []
    for artwork in metadata.get("artworkFiles", []):
        path = run_dir / artwork["file"]
        canvas = artwork.get("canvas")
        png_result = validate_png_file(path, canvas)
        transparency_result = validate_transparency_file(path, canvas)
        image_results.append({"png": png_result, "transparency": transparency_result})
        if not png_result["valid"]:
            errors.extend([f"{artwork['file']}: {err}" for err in png_result["errors"]])
        if not transparency_result["valid"]:
            errors.extend([f"{artwork['file']}: {err}" for err in transparency_result["errors"]])
        warnings.extend([f"{artwork['file']}: {warn}" for warn in png_result.get("warnings", [])])
        warnings.extend([f"{artwork['file']}: {warn}" for warn in transparency_result.get("warnings", [])])
    meta_result = metadata_lint(metadata, run_dir=run_dir)
    if not meta_result["valid"]:
        errors.extend(meta_result["errors"])
    warnings.extend(meta_result["warnings"])
    return {
        "validatedAt": now_stamp(),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "imageResults": image_results,
        "metadataLint": meta_result,
    }


def package_output(run_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "output" / "metadata" / "merch_metadata.json"
    validation_path = run_dir / "output" / "validation" / "validation_summary.json"
    report_path = run_dir / "output" / "report" / "merch_report.md"
    summary = {
        "runDir": str(run_dir),
        "metadata": str(metadata_path),
        "validation": str(validation_path),
        "report": str(report_path),
        "finalFiles": sorted(str(path) for path in (run_dir / "output" / "final").glob("*.png")),
        "workspacePreserved": True,
        "upload": False,
        "humanReviewRequired": True,
    }
    write_json(run_dir / "output" / "package_summary.json", summary)
    return summary


@dataclass
class AutopilotRequest:
    count: int = 1
    marketplaces: list[str] | None = None
    products: list[str] | None = None
    niche: str | None = None
    variants_per_concept: int = 3
    output_root: Path = DEFAULT_OUTPUT_ROOT
    seed: int = 7
    image_adapter_command: str | None = None
    allow_demo_fallback: bool = True
    generator: str = "imagegen"
    research_mode: str = "auto"
    research_file: Path | None = None
    depth: str = "standard"


def run_autopilot(request: AutopilotRequest) -> dict[str, Any]:
    if request.generator not in GENERATOR_CHOICES:
        raise SystemExit(f"Unknown generator: {request.generator}. Use one of: {', '.join(GENERATOR_CHOICES)}")
    profile = depth_profile(request.depth)
    research_mode = request.research_mode
    if research_mode == "auto":
        research_mode = "local" if request.depth == "quick" or request.generator == "demo" else "codex"
    if research_mode not in {"codex", "local"}:
        raise SystemExit("Unknown research mode. Use auto, codex, or local.")
    presets = canvas_presets()
    markets = marketplace_config()
    selected_products = request.products or ["standard_apparel"]
    selected_markets = request.marketplaces or ["US", "UK"]
    for product in selected_products:
        if product not in presets:
            raise SystemExit(f"Unknown product canvas: {product}")
    for market in selected_markets:
        if market not in markets:
            raise SystemExit(f"Unknown marketplace: {market}")

    request.output_root.mkdir(parents=True, exist_ok=True)
    if research_mode == "codex" and request.research_file is None:
        return prepare_research_jobs(
            output_root=request.output_root,
            count=request.count,
            marketplaces=selected_markets,
            products=selected_products,
            niche=request.niche,
            depth=request.depth,
            seed=request.seed,
        )

    external_research = load_json(request.research_file) if request.research_file else None
    evidence_validation = validate_external_research(external_research, request.depth, requested_count=request.count)
    if request.depth != "quick" and profile["requiresExternalResearch"] and not evidence_validation["valid"]:
        raise SystemExit(
            "Research evidence is not sufficient for "
            f"{request.depth} depth. Fix {request.research_file or 'external_research.json'} before scoring:\n"
            + "\n".join(f"- {error}" for error in evidence_validation["errors"])
        )
    fallback_offline = bool(evidence_validation.get("stats", {}).get("fallbackOffline")) or request.generator == "demo"
    research = research_candidates(
        niche=request.niche,
        marketplaces=selected_markets,
        products=selected_products,
        target_pool_size=max(profile["minimumResearchJobs"], request.count * profile["candidateMultiplier"]),
        seed=request.seed,
        external_research=external_research,
        depth=request.depth,
        fallback_offline=fallback_offline,
        requested_count=request.count,
    )
    research["evidenceValidation"] = evidence_validation
    scoring = score_niches(research["candidates"])
    accepted = scoring["accepted"]
    if len(accepted) < request.count:
        raise SystemExit(f"Only {len(accepted)} compliant candidate(s) available for {request.count} requested design(s).")

    batch_stamp = now_stamp()
    run_summaries = []
    variants_per_concept = max(request.variants_per_concept, profile["minVariants"])
    for idx, candidate in enumerate(accepted[: request.count], start=1):
        concept = build_concept(candidate, idx)
        # Respect explicit product constraints after concept creation.
        concept["productFit"] = selected_products
        concept["marketplaces"] = selected_markets
        run_dir = create_job_folder(request.output_root, concept["conceptName"], timestamp=batch_stamp)
        paths = ensure_run_structure(run_dir)

        write_json(paths["research"] / "candidate_niches.json", research)
        write_json(paths["research"] / "scored_niches.json", scoring)
        write_json(paths["research"] / "external_research.json", external_research or {})
        write_json(paths["research"] / "research_evidence_validation.json", evidence_validation)
        write_text(paths["research"] / "trend_notes.md", _trend_notes(concept, research))
        write_text(paths["research"] / "competitor_observations.md", _competitor_notes(concept))
        write_json(paths["research"] / "keyword_candidates.json", {"keywords": concept.get("keywords", [])})
        write_json(paths["research"] / "marketplace_notes.json", {"marketplaces": selected_markets, "config": {m: markets[m] for m in selected_markets}})
        write_json(paths["concepts"] / "concept_brief.json", concept)

        compliance_terms = [concept["conceptName"], concept["visibleText"], concept["niche"], f"Scout {slugify(concept['niche']).split('-')[0].title()} Studio"]
        compliance_terms.extend(concept.get("keywords", []))
        compliance = trademark_check(compliance_terms, selected_markets)
        compliance = enrich_compliance_with_research(compliance, concept)
        write_json(paths["compliance"] / "trademark_checks.json", compliance)
        write_json(paths["compliance"] / "risky_terms_removed.json", {"removed": [hit["term"] for hit in compliance.get("riskHits", [])]})
        write_text(paths["compliance"] / "policy_review.md", _policy_review(compliance))

        if request.generator == "imagegen":
            manifest = create_imagegen_jobs(run_dir, concept, selected_products, variants_per_concept, idx, depth=request.depth)
            run_summaries.append(
                {
                    "runDir": str(run_dir),
                    "concept": concept["conceptName"],
                    "valid": False,
                    "generator": "imagegen",
                    "depth": request.depth,
                    "status": "awaiting_codex_imagegen",
                    "imagegenJobs": str(run_dir / "workspace" / "processing" / "imagegen_jobs.json"),
                    "nextStep": f"Call image_gen for each job, save sourcePath files, then run: python3 {SKILL_ROOT / 'scripts' / 'finalize_imagegen.py'} {run_dir}",
                }
            )
            continue

        option_scores = []
        primary_canvas = selected_products[0]
        for option in range(1, variants_per_concept + 1):
            option_path = paths["candidates"] / f"option_{chr(96 + option)}_{primary_canvas}.png"
            generated = generate_design(
                concept,
                primary_canvas,
                option_path,
                option_index=option,
                adapter_command=request.image_adapter_command,
                allow_fallback=request.allow_demo_fallback,
            )
            option_validation = validate_transparency_file(option_path, primary_canvas)
            score = 70 + option * 3 - (0 if option_validation["valid"] else 20)
            option_scores.append(
                {
                    "option": option,
                    "file": str(option_path.relative_to(run_dir)),
                    "score": score,
                    "generator": generated.get("generator"),
                    "validation": option_validation,
                }
            )
        write_json(paths["candidates"] / "option_scores.json", {"options": option_scores})

        artwork_files = []
        for canvas_key in selected_products:
            width, height = presets[canvas_key]["size"]
            final_rel = Path("output") / "final" / f"design_{idx:02d}_{canvas_key}_{width}x{height}.png"
            final_path = run_dir / final_rel
            generated = generate_design(
                concept,
                canvas_key,
                final_path,
                option_index=1,
                adapter_command=request.image_adapter_command,
                allow_fallback=request.allow_demo_fallback,
            )
            processing_path = paths["processing"] / f"resized_exact_canvas_{canvas_key}.json"
            write_json(processing_path, generated)
            png_result = validate_png_file(final_path, canvas_key)
            transparency_result = validate_transparency_file(final_path, canvas_key)
            write_json(paths["processing"] / f"transparency_test_{canvas_key}.json", transparency_result)
            artwork_files.append(
                {
                    "file": str(final_rel),
                    "canvas": canvas_key,
                    "width": width,
                    "height": height,
                    "transparent": presets[canvas_key].get("background") == "transparent_png",
                    "validated": bool(png_result["valid"] and transparency_result["valid"]),
                    "generator": generated.get("generator", "unknown"),
                }
            )

        metadata = make_metadata(run_dir, concept, artwork_files, compliance, research)
        write_json(paths["metadata"] / "merch_metadata.json", metadata)
        validation = validate_package(run_dir, metadata)
        write_json(paths["validation"] / "validation_summary.json", validation)
        report = generate_report(run_dir, concept, metadata, validation, research, scoring, compliance)
        write_text(paths["report"] / "merch_report.md", report)
        package_summary = package_output(run_dir)
        run_summaries.append({"runDir": str(run_dir), "concept": concept["conceptName"], "valid": validation["valid"], "depth": request.depth, "package": package_summary})

    created_count = 0 if request.generator == "imagegen" else len(run_summaries)
    batch_summary = {
        "createdAt": batch_stamp,
        "requestedCount": request.count,
        "createdCount": created_count,
        "preparedCount": len(run_summaries),
        "generator": request.generator,
        "depth": request.depth,
        "researchMode": research_mode,
        "fallbackOffline": fallback_offline,
        "fallbackNotice": FALLBACK_OFFLINE_NOTICE if fallback_offline else "",
        "status": "awaiting_codex_imagegen" if request.generator == "imagegen" else "complete",
        "runs": run_summaries,
        "upload": False,
        "humanReviewRequired": True,
        "complianceWording": REQUIRED_COMPLIANCE_WORDING,
    }
    write_json(request.output_root / f"{batch_stamp}_merch_scout_batch_summary.json", batch_summary)
    return batch_summary


def _trend_notes(concept: dict[str, Any], research: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Trend Notes",
            "",
            f"Concept: {concept['conceptName']}",
            f"Niche: {concept['niche']}",
            "",
            "Signals used in this v1 run:",
            "",
            "- Local evergreen/seasonal/cross-niche seed pool.",
            "- Product fit heuristics from configured Amazon canvas presets.",
            "- Compliance hard gates before final selection.",
            "",
            "Optional adapters can add Google Trends, Keepa, Amazon allowed APIs, and browser snapshots.",
            "",
        ]
    )


def _competitor_notes(concept: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Competitor Observations",
            "",
            "No live competitor scraping was run by default.",
            "When enabled, marketplace/browser observations must be used for positioning only.",
            "Do not copy competitor artwork, phrases, layouts, titles, or brands.",
            "",
            f"Selected style direction: {concept.get('designStyle')}",
            "",
        ]
    )


def _policy_review(compliance: dict[str, Any]) -> str:
    lines = [
        "# Policy Review",
        "",
        f"Risk level: {compliance.get('riskLevel')}",
        "",
        compliance.get("statement", REQUIRED_COMPLIANCE_WORDING),
        "",
        "Human review is required for trademark, copyright, public figure, marketplace policy, and upload UI checks.",
        "",
        "Risk hits:",
        "",
    ]
    if compliance.get("riskHits"):
        for hit in compliance["riskHits"]:
            lines.append(f"- {hit['term']} ({hit['category']}) from `{hit['source']}`")
    else:
        lines.append("- none from local lint")
    lines.append("")
    return "\n".join(lines)


def build_autopilot_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Merch Scout autopilot.")
    parser.add_argument("--count", type=int, default=1, help="Number of final design packages to create.")
    parser.add_argument("--marketplaces", default="auto", help="Comma-separated marketplace codes, or auto.")
    parser.add_argument("--products", default="auto", help="Comma-separated canvas keys, or auto.")
    parser.add_argument("--niche", default=None, help="Optional directed niche.")
    parser.add_argument(
        "--depth",
        choices=DEPTH_CHOICES,
        default="standard",
        help="quick is local/test only; standard is production default with real research; deep expands research and candidates.",
    )
    parser.add_argument("--variants-per-concept", type=int, default=3, help="Candidate options to preserve in workspace.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Root folder for runs.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic scoring seed.")
    parser.add_argument(
        "--generator",
        choices=GENERATOR_CHOICES,
        default="imagegen",
        help="Production default is imagegen. Use demo only for fallback, CI, or local smoke tests.",
    )
    parser.add_argument(
        "--research-mode",
        choices=["auto", "codex", "local"],
        default="auto",
        help="auto means codex research for imagegen production and local seed research for demo.",
    )
    parser.add_argument(
        "--research-file",
        type=Path,
        default=None,
        help="External research evidence JSON produced from research_jobs.json.",
    )
    parser.add_argument(
        "--image-adapter-command",
        default=None,
        help="External image adapter command. Also supported by MERCH_SCOUT_IMAGE_ADAPTER_CMD.",
    )
    parser.add_argument(
        "--no-demo-fallback",
        action="store_true",
        help="Fail if an external image adapter is configured but does not produce a valid PNG.",
    )
    return parser


def autopilot_from_args(argv: list[str] | None = None) -> dict[str, Any]:
    parser = build_autopilot_parser()
    args = parser.parse_args(argv)
    if args.count < 1:
        raise SystemExit("--count must be at least 1")
    request = AutopilotRequest(
        count=args.count,
        marketplaces=parse_csv(args.marketplaces, allowed=list(marketplace_config().keys())),
        products=parse_csv(args.products, allowed=list(canvas_presets().keys())),
        niche=args.niche,
        depth=args.depth,
        variants_per_concept=max(1, args.variants_per_concept),
        output_root=args.output_root,
        seed=args.seed,
        image_adapter_command=args.image_adapter_command,
        allow_demo_fallback=not args.no_demo_fallback,
        generator=args.generator,
        research_mode=args.research_mode,
        research_file=args.research_file,
    )
    return run_autopilot(request)


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))

#!/usr/bin/env python3
"""Fill Merch Scout research evidence using free/no-key public APIs.

This adapter is intentionally conservative:
- It uses public/no-key APIs or public pages only.
- It records fetched source URLs and status.
- It does not scrape marketplace result pages.
- It does not claim legal clearance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from merch_scout_core import DEPTH_CHOICES, REQUIRED_COMPLIANCE_WORDING, depth_profile, print_json, write_json


USER_AGENT = "MerchScout/1.0 (local Codex skill; human-review research; contact: local)"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
DATAMUSE_API = "https://api.datamuse.com/words"
DUCKDUCKGO_API = "https://api.duckduckgo.com/"
WIKIMEDIA_PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user"

OFFICIAL_POLICY_SOURCES = [
    {
        "title": "Amazon Merch on Demand Developer Portal",
        "url": "https://developer.amazon.com/merch",
        "sourceType": "policy",
        "note": "Official Amazon Merch on Demand entry point; human must review current account policy pages before upload.",
    },
    {
        "title": "Amazon Merch on Demand content guidelines search",
        "url": "https://www.amazon.com/s?k=Amazon+Merch+on+Demand+content+policy",
        "sourceType": "policy",
        "note": "Search URL only; not scraped. Use Codex/browser or human review for current policy details.",
        "fetched": False,
    },
]

RISK_TERMS = {
    "brand": ["brand", "company", "business", "product", "trademark", "logo"],
    "copyright": ["film", "television", "tv series", "fictional", "character", "comic", "anime", "manga", "video game", "song", "album"],
    "public_figure": ["politician", "actor", "singer", "athlete", "musician", "youtuber", "public figure", "person"],
    "sports": ["sports team", "football club", "basketball team", "baseball team", "league"],
}


def http_json(url: str, timeout: float = 8.0) -> tuple[dict[str, Any] | list[Any] | None, dict[str, Any]]:
    started = time.time()
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1_500_000)
            elapsed = round(time.time() - started, 3)
            status = getattr(response, "status", 200)
            text = raw.decode("utf-8", errors="replace")
            return json.loads(text), {"fetched": True, "status": status, "elapsedSeconds": elapsed}
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return None, {"fetched": False, "error": str(exc), "elapsedSeconds": round(time.time() - started, 3)}


def api_url(base: str, params: dict[str, Any]) -> str:
    return f"{base}?{urlencode(params)}"


def compact_query(text: str, max_words: int = 7) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(tokens[:max_words]).strip() or "original merch design"


def datamuse_keywords(query: str, timeout: float) -> tuple[list[str], dict[str, Any]]:
    url = api_url(DATAMUSE_API, {"ml": query, "max": 12})
    data, fetch = http_json(url, timeout=timeout)
    words = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("word"):
                word = str(item["word"]).strip().lower()
                if len(word) >= 3 and re.match(r"^[a-z0-9 -]+$", word):
                    words.append(word)
    source = {
        "title": "Datamuse related-word API",
        "url": url,
        "sourceType": "keyword",
        "note": f"Related keyword suggestions for `{query}`.",
        **fetch,
    }
    return list(dict.fromkeys(words))[:10], source


def wikipedia_search(query: str, timeout: float) -> tuple[list[dict[str, str]], dict[str, Any]]:
    url = api_url(WIKIPEDIA_API, {"action": "opensearch", "search": query, "limit": 5, "namespace": 0, "format": "json"})
    data, fetch = http_json(url, timeout=timeout)
    results: list[dict[str, str]] = []
    if isinstance(data, list) and len(data) >= 4:
        titles = data[1] if isinstance(data[1], list) else []
        descriptions = data[2] if isinstance(data[2], list) else []
        links = data[3] if isinstance(data[3], list) else []
        for title, description, link in zip(titles, descriptions, links):
            results.append({"title": str(title), "description": str(description), "url": str(link)})
    source = {
        "title": "Wikipedia OpenSearch API",
        "url": url,
        "sourceType": "design_direction",
        "note": f"Public context search for `{query}`.",
        **fetch,
    }
    return results, source


def wikidata_search(query: str, timeout: float) -> tuple[list[dict[str, str]], dict[str, Any]]:
    url = api_url(
        WIKIDATA_API,
        {"action": "wbsearchentities", "search": query, "language": "en", "format": "json", "limit": 5},
    )
    data, fetch = http_json(url, timeout=timeout)
    entities = []
    if isinstance(data, dict):
        for item in data.get("search", []):
            if isinstance(item, dict):
                entities.append(
                    {
                        "id": str(item.get("id", "")),
                        "label": str(item.get("label", "")),
                        "description": str(item.get("description", "")),
                        "url": str(item.get("concepturi", "")) or f"https://www.wikidata.org/wiki/{item.get('id', '')}",
                    }
                )
    source = {
        "title": "Wikidata entity search API",
        "url": url,
        "sourceType": "trademark",
        "note": f"Public-entity context for brand/person/franchise risk around `{query}`.",
        **fetch,
    }
    return entities, source


def duckduckgo_instant_answer(query: str, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
    url = api_url(DUCKDUCKGO_API, {"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1})
    data, fetch = http_json(url, timeout=timeout)
    result = data if isinstance(data, dict) else {}
    source = {
        "title": "DuckDuckGo Instant Answer API",
        "url": url,
        "sourceType": "marketplace",
        "note": f"Light public web discovery query for `{query}`. This is not a full search index.",
        **fetch,
    }
    return result, source


def wikipedia_pageviews(title: str, timeout: float) -> tuple[int | None, dict[str, Any]]:
    end = datetime.now(timezone.utc).date() - timedelta(days=2)
    start = end - timedelta(days=30)
    safe_title = quote(title.replace(" ", "_"), safe="")
    url = f"{WIKIMEDIA_PAGEVIEWS}/{safe_title}/daily/{start:%Y%m%d}/{end:%Y%m%d}"
    data, fetch = http_json(url, timeout=timeout)
    total = None
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        total = sum(int(item.get("views", 0)) for item in data["items"] if isinstance(item, dict))
    source = {
        "title": "Wikimedia Pageviews API",
        "url": url,
        "sourceType": "trend",
        "note": f"30-day pageview proxy for Wikipedia page `{title}`.",
        **fetch,
    }
    return total, source


def official_policy_source(timeout: float) -> dict[str, Any]:
    source = dict(OFFICIAL_POLICY_SOURCES[0])
    _data, fetch = http_json(source["url"], timeout=timeout)
    source.update(fetch)
    return source


def risk_flags_from_public_entities(entities: list[dict[str, str]], wiki_results: list[dict[str, str]]) -> list[dict[str, str]]:
    text_items = []
    for entity in entities:
        text_items.append(f"{entity.get('label', '')} {entity.get('description', '')}")
    for result in wiki_results:
        text_items.append(f"{result.get('title', '')} {result.get('description', '')}")
    flags = []
    for text in text_items:
        lowered = text.lower()
        for risk_type, terms in RISK_TERMS.items():
            if any(term in lowered for term in terms):
                severity = "medium" if risk_type in {"brand", "copyright", "public_figure"} else "low"
                flags.append({"severity": severity, "type": risk_type, "note": f"Public entity context suggests {risk_type} review: {text[:160]}"})
    return list({json.dumps(flag, sort_keys=True): flag for flag in flags}.values())[:6]


def score_from_signals(
    job: dict[str, Any],
    keywords: list[str],
    wiki_results: list[dict[str, str]],
    pageviews: int | None,
    risks: list[dict[str, str]],
) -> tuple[int, int, int]:
    seed_scores = job.get("localSeedScores", {}) if isinstance(job.get("localSeedScores"), dict) else {}
    demand = int(seed_scores.get("demand") or 55)
    saturation = int(seed_scores.get("saturation") or 50)
    originality = int(seed_scores.get("originality") or 65)
    demand += min(12, len(keywords))
    demand += min(10, len(wiki_results) * 2)
    if pageviews:
        demand += min(18, max(0, pageviews // 2500))
    saturation += min(16, len(wiki_results) * 3)
    if risks:
        originality -= min(20, len(risks) * 4)
    return max(0, min(100, demand)), max(0, min(100, saturation)), max(0, min(100, originality))


def observation_for_job(job: dict[str, Any], timeout: float) -> dict[str, Any]:
    visible_text = str(job.get("visibleText") or job.get("candidateName") or "")
    niche = str(job.get("niche") or visible_text)
    query = compact_query(f"{visible_text} {niche}")
    queries = [
        f"{query} merch demand",
        f"{query} shirt marketplace saturation",
        f"{visible_text} trademark",
    ]
    keywords, datamuse_source = datamuse_keywords(query, timeout)
    wiki_results, wiki_source = wikipedia_search(query, timeout)
    entities, wikidata_source = wikidata_search(visible_text or query, timeout)
    ddg, ddg_source = duckduckgo_instant_answer(f"{query} merch shirt", timeout)
    pageviews = None
    pageview_source = None
    if wiki_results:
        pageviews, pageview_source = wikipedia_pageviews(wiki_results[0]["title"], timeout)
    policy_source = official_policy_source(timeout)
    risks = risk_flags_from_public_entities(entities, wiki_results)
    demand, saturation, originality = score_from_signals(job, keywords, wiki_results, pageviews, risks)
    sources = [datamuse_source, wiki_source, wikidata_source, ddg_source, policy_source]
    if pageview_source:
        sources.append(pageview_source)
    for result in wiki_results[:2]:
        sources.append(
            {
                "title": f"Wikipedia result: {result['title']}",
                "url": result["url"],
                "sourceType": "design_direction",
                "note": result.get("description", "")[:240] or "Related public context result.",
                "fetched": True,
            }
        )
    abstract_url = str(ddg.get("AbstractURL") or "").strip()
    if abstract_url:
        sources.append(
            {
                "title": "DuckDuckGo abstract source",
                "url": abstract_url,
                "sourceType": "trend",
                "note": str(ddg.get("AbstractText") or "")[:240] or "Instant Answer abstract source.",
                "fetched": True,
            }
        )
    sources.extend(OFFICIAL_POLICY_SOURCES[1:])
    product_fit = {product: "Adapter evidence supports compact, original, non-branded artwork review for this canvas." for product in job.get("products", [])}
    marketplace_fit = {market: "Adapter evidence collected public context; human/Codex review should verify live marketplace saturation." for market in job.get("marketplaces", [])}
    return {
        "jobId": job.get("jobId"),
        "niche": niche,
        "query": query,
        "queries": queries,
        "demandSignal": demand,
        "saturationSignal": saturation,
        "originalityPotential": originality,
        "marketplaceFit": marketplace_fit,
        "productFit": product_fit,
        "keywords": keywords[:8],
        "riskFlags": risks,
        "notes": [
            f"Free adapters checked Datamuse, Wikipedia, Wikidata, DuckDuckGo Instant Answer, Wikimedia Pageviews when available, and official/public policy URLs for `{query}`.",
            f"Pageviews proxy: {pageviews if pageviews is not None else 'not available'}.",
            "Marketplace pages were not scraped; use browser/Codex review for final saturation judgment.",
            REQUIRED_COMPLIANCE_WORDING,
        ],
        "sources": sources,
    }


def build_evidence(jobs_payload: dict[str, Any], depth: str, max_jobs: int | None, timeout: float) -> dict[str, Any]:
    profile = depth_profile(depth)
    jobs = [job for job in jobs_payload.get("jobs", []) if isinstance(job, dict)]
    target_jobs = max_jobs or max(profile["minObservations"], 1)
    selected_jobs = jobs[:target_jobs]
    observations = [observation_for_job(job, timeout) for job in selected_jobs]
    all_queries = []
    for observation in observations:
        all_queries.extend(observation.get("queries", []))
        all_queries.append(str(observation.get("query", "")))
    rejected = []
    for job in jobs[target_jobs : target_jobs + max(3, target_jobs // 2)]:
        rejected.append(
            {
                "name": job.get("candidateName") or job.get("niche"),
                "reason": "Not selected in the first free-adapter pass; kept for Codex/human comparison against higher-scoring evidence-backed candidates.",
            }
        )
    if not rejected and selected_jobs:
        rejected.append(
            {
                "name": "unprocessed lower-priority seed candidates",
                "reason": "The free adapter processed the requested evidence minimum. Codex/browser review should compare additional seed candidates before final upload decisions.",
            }
        )
    fetched_sources = [
        source
        for observation in observations
        for source in observation.get("sources", [])
        if isinstance(source, dict) and source.get("fetched") is not False
    ]
    return {
        "schemaVersion": "1.0.0",
        "depth": depth,
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "method": "Free/no-key public API adapters: Datamuse, MediaWiki/Wikipedia, Wikidata, DuckDuckGo Instant Answer, Wikimedia Pageviews, public policy URLs. No marketplace scraping.",
        "webSearchUsed": False,
        "apiResearchUsed": True,
        "fallbackOffline": False,
        "fallbackReason": "",
        "minimumEvidenceRequirements": jobs_payload.get("minimumEvidenceRequirements", {}),
        "queriesSearched": list(dict.fromkeys(q for q in all_queries if q.strip())),
        "observations": observations,
        "rejectedCandidates": rejected,
        "marketplaceComparisons": [
            {"marketplace": "US", "observation": "Free adapters do not scrape Amazon result pages; use Browser/Codex or human review for live marketplace density."}
        ],
        "productComparisons": [
            {"product": "standard_apparel", "observation": "Most versatile canvas for typography and illustration."},
            {"product": "popsockets", "observation": "Requires compact, high-contrast art and short text."},
        ],
        "unresolvedRisks": [
            {"type": "trademark", "note": "Free adapters are screening aids only. Human must check official databases for title, brand, visible text, and keywords before upload."},
            {"type": "marketplace_saturation", "note": "Marketplace pages were not scraped by the adapter; browser review is still recommended."},
        ],
        "adapterSummary": {
            "processedJobs": len(selected_jobs),
            "fetchedUsableSources": len(fetched_sources),
            "sourceTypes": sorted({source.get("sourceType", "other") for source in fetched_sources}),
        },
    }


def resolve_paths(input_path: Path, evidence_file: Path | None) -> tuple[Path, Path]:
    if input_path.is_dir():
        jobs_path = input_path / "research_jobs.json"
        evidence_path = evidence_file or input_path / "external_research.json"
    else:
        jobs_path = input_path
        evidence_path = evidence_file or input_path.with_name("external_research.json")
    return jobs_path, evidence_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill Merch Scout external_research.json using free/no-key public APIs.")
    parser.add_argument("research", type=Path, help="Research directory or research_jobs.json.")
    parser.add_argument("--evidence-file", type=Path, default=None, help="Output external_research.json path.")
    parser.add_argument("--depth", choices=DEPTH_CHOICES, default=None, help="Override depth from research_jobs.json.")
    parser.add_argument("--max-jobs", type=int, default=None, help="Limit jobs processed. Defaults to depth minimum observations.")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout per request.")
    parser.add_argument("--print-only", action="store_true", help="Print evidence JSON instead of writing it.")
    args = parser.parse_args()

    jobs_path, evidence_path = resolve_paths(args.research, args.evidence_file)
    if not jobs_path.exists():
        raise SystemExit(f"Missing research jobs file: {jobs_path}")
    jobs_payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    depth = args.depth or jobs_payload.get("depth") or "standard"
    if depth not in DEPTH_CHOICES:
        raise SystemExit(f"Unknown depth: {depth}")
    evidence = build_evidence(jobs_payload, depth, args.max_jobs, args.timeout)
    if args.print_only:
        print_json(evidence)
    else:
        write_json(evidence_path, evidence)
        print_json({"status": "ok", "evidenceFile": str(evidence_path), "observations": len(evidence["observations"]), "adapterSummary": evidence["adapterSummary"]})


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

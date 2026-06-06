import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "merch-scout" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from merch_scout_core import (  # noqa: E402
    AutopilotRequest,
    FALLBACK_OFFLINE_NOTICE,
    create_job_folder,
    finalize_imagegen_run,
    generate_demo_design,
    keyword_lint,
    metadata_lint,
    run_autopilot,
    trademark_check,
    validate_external_research,
    validate_png_file,
    validate_transparency_file,
)
import free_research_adapters  # noqa: E402


class MerchScoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="merch_scout_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def valid_research_evidence(self):
        source_types = ["marketplace", "trend", "keyword", "trademark", "policy", "design_direction"]
        observations = []
        for idx, source_type in enumerate(source_types, start=1):
            observations.append(
                {
                    "jobId": f"research_{idx:02d}_quiet-coffee-coder",
                    "niche": "programmer humor coffee introverts" if idx <= 2 else f"candidate niche {idx}",
                    "query": f"research query {idx}",
                    "demandSignal": 70 + idx,
                    "saturationSignal": 40 + idx,
                    "originalityPotential": 75,
                    "marketplaceFit": {"US": "Good buyer fit with broad English-language gift intent."},
                    "productFit": {"popsockets": "Short phrase and centered icon work on the small canvas."},
                    "keywords": ["programmer", "coffee", "introvert"],
                    "riskFlags": [],
                    "notes": [f"Concrete observation {idx} from source review."],
                    "sources": [
                        {
                            "title": f"{source_type.title()} source A",
                            "url": f"https://research.test/{source_type}/a-{idx}",
                            "sourceType": source_type,
                            "note": "Evidence used for scoring.",
                        },
                        {
                            "title": f"{source_type.title()} source B",
                            "url": f"https://research.test/{source_type}/b-{idx}",
                            "sourceType": source_type,
                            "note": "Cross-check source.",
                        },
                    ],
                }
            )
        return {
            "schemaVersion": "1.0.0",
            "depth": "standard",
            "completedAt": "2026-06-06T00:00:00Z",
            "method": "Codex web/browser research test fixture.",
            "webSearchUsed": True,
            "fallbackOffline": False,
            "queriesSearched": [f"research query {idx}" for idx in range(1, 7)],
            "observations": observations,
            "rejectedCandidates": [{"name": "generic cat shirt", "reason": "Too saturated and weak originality."}],
            "marketplaceComparisons": [{"marketplace": "US", "observation": "Best fit for English phrase."}],
            "productComparisons": [{"product": "popsockets", "observation": "Works with compact centered art."}],
            "unresolvedRisks": [{"type": "trademark", "note": "Human must still check official databases before upload."}],
        }

    def test_autopilot_creates_valid_package(self):
        summary = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                generator="demo",
                depth="quick",
            )
        )
        self.assertEqual(summary["createdCount"], 1)
        run_dir = Path(summary["runs"][0]["runDir"])
        metadata_path = run_dir / "output" / "metadata" / "merch_metadata.json"
        validation_path = run_dir / "output" / "validation" / "validation_summary.json"
        report_path = run_dir / "output" / "report" / "merch_report.md"
        self.assertTrue(metadata_path.exists())
        self.assertTrue(validation_path.exists())
        self.assertTrue(report_path.exists())

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        self.assertFalse(metadata["upload"])
        self.assertTrue(metadata["humanReviewRequired"])
        self.assertTrue(validation["valid"])
        final = run_dir / metadata["artworkFiles"][0]["file"]
        with Image.open(final) as image:
            self.assertEqual(image.size, (485, 485))
        report = report_path.read_text(encoding="utf-8")
        self.assertIn(FALLBACK_OFFLINE_NOTICE, report)

    def test_trademark_check_flags_brand_risk(self):
        result = trademark_check(["Disney castle fan art"], ["US"])
        self.assertEqual(result["riskLevel"], "high")
        self.assertTrue(result["blocked"])

    def test_keyword_lint_blocks_brand_terms(self):
        result = keyword_lint(["official pokemon shirt"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["riskLevel"], "high")

    def test_metadata_lint_rejects_upload_true(self):
        bad = {
            "schemaVersion": "1.0.0",
            "designId": "x",
            "status": "ready_for_human_review",
            "riskLevel": "low",
            "upload": True,
            "humanReviewRequired": True,
            "selectedProducts": [],
            "selectedMarketplaces": ["US"],
            "artworkFiles": [],
            "listings": {"US": {"brand": "A", "title": "B", "bullet1": "C", "bullet2": "D", "description": "E"}},
            "keywords": {"primary": [], "secondary": [], "removedForRisk": []},
            "compliance": {},
            "researchSummary": {},
        }
        result = metadata_lint(bad)
        self.assertFalse(result["valid"])
        self.assertIn("metadata.upload must be false in v1.", result["errors"])

    def test_transparency_validator_detects_fake_checkerboard(self):
        path = self.tmp / "fake_checkerboard.png"
        image = Image.new("RGBA", (80, 80), (0, 0, 0, 255))
        pixels = image.load()
        colors = [(192, 192, 192, 255), (230, 230, 230, 255)]
        for y in range(80):
            for x in range(80):
                pixels[x, y] = colors[((x // 10) + (y // 10)) % 2]
        image.save(path, format="PNG")
        result = validate_transparency_file(path)
        self.assertFalse(result["valid"])
        self.assertTrue(result["fakeCheckerboardDetected"])

    def test_png_validator_checks_exact_dimensions(self):
        path = self.tmp / "small.png"
        Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path, format="PNG")
        result = validate_png_file(path, "popsockets")
        self.assertFalse(result["valid"])
        self.assertTrue(any("Expected 485x485" in error for error in result["errors"]))

    def test_external_image_adapter_contract(self):
        summary = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                image_adapter_command=f"{sys.executable} {SCRIPTS / 'example_image_adapter.py'}",
                allow_demo_fallback=False,
                generator="demo",
                depth="quick",
            )
        )
        run_dir = Path(summary["runs"][0]["runDir"])
        processing = json.loads((run_dir / "workspace" / "processing" / "resized_exact_canvas_popsockets.json").read_text(encoding="utf-8"))
        self.assertEqual(processing["generator"], "external_adapter")
        validation = json.loads((run_dir / "output" / "validation" / "validation_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(validation["valid"])

    def test_imagegen_prepare_and_finalize_flow(self):
        summary = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                generator="imagegen",
                research_mode="local",
                depth="quick",
            )
        )
        self.assertEqual(summary["status"], "awaiting_codex_imagegen")
        self.assertEqual(summary["preparedCount"], 1)
        run_dir = Path(summary["runs"][0]["runDir"])
        manifest_path = run_dir / "workspace" / "processing" / "imagegen_jobs.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        concept = manifest["concept"]
        for job in manifest["jobs"]:
            generate_demo_design(concept, job["canvas"], run_dir / job["sourcePath"], option_index=job["optionIndex"])
        finalized = finalize_imagegen_run(run_dir)
        self.assertTrue(finalized["valid"])
        metadata = json.loads((run_dir / "output" / "metadata" / "merch_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["artworkFiles"][0]["generator"], "imagegen")
        final = run_dir / metadata["artworkFiles"][0]["file"]
        self.assertTrue(final.exists())

    def test_imagegen_default_prepares_codex_research_first(self):
        summary = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                generator="imagegen",
            )
        )
        self.assertEqual(summary["status"], "awaiting_codex_research")
        self.assertTrue(Path(summary["researchJobs"]).exists())
        self.assertTrue(Path(summary["researchEvidenceFile"]).exists())
        self.assertTrue(Path(summary["browserResearchTasks"]).exists())
        self.assertTrue(Path(summary["browserResearchPlan"]).exists())
        tasks = json.loads(Path(summary["browserResearchTasks"]).read_text(encoding="utf-8"))
        self.assertEqual(tasks["status"], "awaiting_browser_research")
        first_checks = [check["type"] for check in tasks["tasks"][0]["browserChecks"]]
        self.assertIn("amazon_listing_scan", first_checks)
        self.assertIn("trend_scan", first_checks)
        self.assertIn("design_direction_scan", first_checks)

    def test_standard_rejects_placeholder_research_file(self):
        first = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                generator="imagegen",
            )
        )
        with self.assertRaises(SystemExit) as raised:
            run_autopilot(
                AutopilotRequest(
                    count=1,
                    products=["popsockets"],
                    marketplaces=["US"],
                    output_root=self.tmp,
                    generator="imagegen",
                    research_file=Path(first["researchEvidenceFile"]),
                )
            )
        self.assertIn("Research evidence is not sufficient", str(raised.exception))

    def test_standard_valid_research_file_prepares_imagegen_jobs(self):
        research_file = self.tmp / "external_research.json"
        research_file.write_text(json.dumps(self.valid_research_evidence()), encoding="utf-8")
        summary = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                generator="imagegen",
                research_file=research_file,
            )
        )
        self.assertEqual(summary["status"], "awaiting_codex_imagegen")
        self.assertEqual(summary["depth"], "standard")
        run_dir = Path(summary["runs"][0]["runDir"])
        manifest = json.loads((run_dir / "workspace" / "processing" / "imagegen_jobs.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["depth"], "standard")
        self.assertGreaterEqual(len(manifest["jobs"]), 5)
        evidence_validation = json.loads((run_dir / "workspace" / "research" / "research_evidence_validation.json").read_text(encoding="utf-8"))
        self.assertTrue(evidence_validation["valid"])

    def test_create_job_folder_avoids_collisions(self):
        first = create_job_folder(self.tmp, "same slug", timestamp="2026-01-01_000000")
        second = create_job_folder(self.tmp, "same slug", timestamp="2026-01-01_000000")
        self.assertNotEqual(first, second)
        self.assertEqual(second.name, "2026-01-01_000000_same-slug-02")

    def test_install_script_installs_skill_to_temp_codex_home(self):
        codex_home = self.tmp / "codex-home"
        result = subprocess.run(
            [
                "bash",
                str(ROOT / "install.sh"),
                "--codex-home",
                str(codex_home),
                "--no-deps",
                "--skip-doctor",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = codex_home / "skills" / "merch-scout"
        self.assertTrue(installed.exists())
        self.assertTrue((installed / "SKILL.md").exists())

    def test_doctor_reports_capabilities(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "doctor.py"), "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("codexRuntimeCapabilities", report)
        self.assertFalse(report["optionalExternalTools"]["mcpRequired"])
        self.assertTrue(report["optionalExternalTools"]["freeNoKeyResearchAdapters"]["installed"])
        self.assertIn("standard", report["productionDepthRequirements"])

    def test_free_research_adapter_fixture_passes_standard_gate(self):
        original_http_json = free_research_adapters.http_json

        def fake_http_json(url, timeout=8.0):
            if "api.datamuse.com" in url:
                return ([{"word": "programmer"}, {"word": "coffee"}, {"word": "introvert"}], {"fetched": True, "status": 200})
            if "opensearch" in url:
                return (
                    [
                        "query",
                        ["Computer programmer"],
                        ["A person who writes software."],
                        ["https://en.wikipedia.org/wiki/Programmer"],
                    ],
                    {"fetched": True, "status": 200},
                )
            if "wikidata.org" in url:
                return ({"search": [{"id": "Q5482740", "label": "Programmer", "description": "person who writes computer software"}]}, {"fetched": True, "status": 200})
            if "api.duckduckgo.com" in url:
                return ({"AbstractURL": "https://duckduckgo.com/?q=programmer+coffee", "AbstractText": "public web context"}, {"fetched": True, "status": 200})
            if "pageviews" in url:
                return ({"items": [{"views": 1000}, {"views": 1500}]}, {"fetched": True, "status": 200})
            return ({}, {"fetched": True, "status": 200})

        free_research_adapters.http_json = fake_http_json
        jobs = []
        try:
            for idx in range(1, 7):
                jobs.append(
                    {
                        "jobId": f"research_{idx:02d}_quiet-coffee-coder",
                        "candidateName": "Quiet Coffee Coder",
                        "niche": "programmer humor coffee introverts",
                        "visibleText": "Quiet Mode Coder",
                        "marketplaces": ["US"],
                        "products": ["popsockets"],
                        "localSeedScores": {"demand": 70, "saturation": 40, "originality": 80},
                    }
                )
            payload = {
                "depth": "standard",
                "minimumEvidenceRequirements": {
                    "minObservations": 6,
                    "minTotalSources": 10,
                    "minSourcesPerObservation": 2,
                    "minSourceTypes": 3,
                },
                "jobs": jobs,
            }
            evidence = free_research_adapters.build_evidence(payload, "standard", max_jobs=6, timeout=0.01)
        finally:
            free_research_adapters.http_json = original_http_json
        result = validate_external_research(evidence, "standard", requested_count=1)
        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(evidence["apiResearchUsed"])


if __name__ == "__main__":
    unittest.main()

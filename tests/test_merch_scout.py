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
    create_job_folder,
    finalize_imagegen_run,
    generate_demo_design,
    keyword_lint,
    metadata_lint,
    run_autopilot,
    trademark_check,
    validate_png_file,
    validate_transparency_file,
)


class MerchScoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="merch_scout_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_autopilot_creates_valid_package(self):
        summary = run_autopilot(
            AutopilotRequest(
                count=1,
                products=["popsockets"],
                marketplaces=["US"],
                output_root=self.tmp,
                generator="demo",
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
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = codex_home / "skills" / "merch-scout"
        self.assertTrue(installed.exists())
        self.assertTrue((installed / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from finalization import finalize_staging


def write_wav(path: Path, frames: int) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\x01\x00" * frames)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class FinalizationTests(unittest.TestCase):
    def test_reports_factory_ready_and_review_pending_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            (staging / "clips").mkdir(parents=True)
            manifests = staging / "manifests"
            manifests.mkdir()
            source = root / "source.wav"
            write_wav(source, 1000)
            for name, review, license_status in (
                ("ready", "REVIEWED", "LICENSE_APPROVED"),
                ("pending", "NEEDS_MUSICAL_REVIEW", "UNREVIEWED"),
            ):
                clip = staging / "clips" / f"{name}.wav"
                write_wav(clip, 400)
                record = {
                    "asset_id": name,
                    "source_path": str(source),
                    "source_sha256": sha(source),
                    "source_start_sample": 100,
                    "source_end_sample": 500,
                    "derived_path": str(clip),
                    "derived_sha256": sha(clip),
                    "review_status": review,
                    "license_status": license_status,
                    "musical_metadata": {
                        "style_family": "POP_PUNK",
                        "instrument_family": "ELECTRIC_GUITAR",
                        "asset_role": "RHYTHM_PATTERN",
                        "tone_family": "CRUNCH",
                    },
                }
                if review == "REVIEWED":
                    record["review_validation"] = {
                        "source_sha256_verified": True,
                        "derived_sha256_verified": True,
                        "sample_boundaries_verified": True,
                        "explicit_musical_approval": True,
                        "explicit_license_approval": True,
                    }
                    record["musical_metadata"].update({
                        "musical_review_notes": "Reviewed by listening.",
                        "license_evidence": "License permits redistribution.",
                    })
                (manifests / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")
            before_source = sha(source)
            result = finalize_staging(staging, reports_root=root / "reports")
            self.assertEqual(result["manifests_checked"], 2)
            report = Path(result["report_directory"]) / "finalization_inventory.csv"
            self.assertTrue(report.is_file())
            report_text = report.read_text(encoding="utf-8-sig")
            self.assertEqual(result["factory_ready_count"], 1, report_text)
            self.assertEqual(result["musical_review_required_count"], 1, report_text)
            self.assertFalse(result["distribution_executed"])
            self.assertEqual(sha(source), before_source)
            summary = json.loads((Path(result["report_directory"]) / "finalization_summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["factory_distribution_allowed"])


if __name__ == "__main__":
    unittest.main()

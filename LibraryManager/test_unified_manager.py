from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from unified_manager import run_manager


def make_test_wav(path: Path, seconds: float = 2.0, rate: int = 8000) -> None:
    frames = []
    for index in range(int(seconds * rate)):
        # A short, repeated amplitude envelope gives the analyzer non-silent audio.
        phase = index / rate
        envelope = 1.0 if (phase % 0.5) < 0.18 else 0.0
        value = int(11000 * envelope * math.sin(2.0 * math.pi * 220.0 * phase))
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"".join(frames))


class UnifiedManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.samples = self.root / "Samples"
        self.incoming = self.samples / "Import Sample Guitar"
        self.incoming.mkdir(parents=True)
        self.reports = self.root / "reports"
        self.wav = self.incoming / "guitar.wav"
        make_test_wav(self.wav)
        self.original_hash = hashlib.sha256(self.wav.read_bytes()).hexdigest().upper()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_inventory_sfz_and_exact_duplicates(self) -> None:
        duplicate = self.incoming / "copy.wav"
        shutil.copyfile(self.wav, duplicate)
        (self.incoming / "instrument.sfz").write_text(
            '<region> sample="guitar.wav" lokey=60 hikey=72 lovel=1 hivel=127\n',
            encoding="utf-8",
        )

        summary = run_manager(self.samples, reports_root=self.reports)
        report_dir = Path(summary["report_directory"])
        self.assertEqual(summary["wav_files"], 2)
        self.assertEqual(summary["sfz_files"], 1)
        self.assertEqual(summary["exact_duplicate_groups"], 1)
        self.assertEqual(summary["sfz_sample_references"], 1)
        self.assertEqual(summary["sfz_missing_references"], 0)
        self.assertTrue((report_dir / "unified_inventory.csv").is_file())
        self.assertTrue((report_dir / "unified_sfz_references.csv").is_file())
        self.assertEqual(hashlib.sha256(self.wav.read_bytes()).hexdigest().upper(),
                         self.original_hash)
        self.assertFalse(summary["source_files_modified"])
        self.assertFalse(summary["automatic_factory_promotion"])

    def test_audio_analysis_is_optional_and_read_only(self) -> None:
        summary = run_manager(
            self.samples, analyze_audio=True, guitar_source_confirmed=False,
            reports_root=self.reports,
        )
        self.assertEqual(summary["audio_files_analyzed"], 1)
        self.assertGreaterEqual(summary["repeated_rhythm_pattern_candidates"], 0)
        self.assertEqual(summary["virtual_active_region_candidates"], 0)
        self.assertEqual(summary["asset_classifications_created"], 1)
        self.assertEqual(summary["classification_policy"], "CANDIDATE_ONLY_REQUIRES_HUMAN_REVIEW")
        classifications = json.loads((Path(summary["report_directory"]) / "unified_asset_classification.json").read_text(encoding="utf-8"))
        self.assertEqual(len(classifications), 1)
        self.assertEqual(classifications[0]["classification_status"], "CANDIDATE_REQUIRES_REVIEW")
        self.assertFalse(classifications[0]["automatic_factory_promotion"])
        self.assertEqual(hashlib.sha256(self.wav.read_bytes()).hexdigest().upper(),
                         self.original_hash)
        self.assertFalse(summary["source_files_moved_or_deleted"])

    def test_virtual_index_requires_explicit_analysis_and_confirmation(self) -> None:
        with self.assertRaises(ValueError):
            run_manager(self.samples, write_virtual=True, reports_root=self.reports)


if __name__ == "__main__":
    unittest.main()

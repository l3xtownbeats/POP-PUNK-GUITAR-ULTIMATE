import hashlib
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from virtual_sample_extractor import analyze_long_wav, write_virtual_index


def write_test_wav(path: Path, rate: int = 11025) -> None:
    samples = []
    # Silence, a sustained guitar-like tone, short gap, second tone, silence.
    for index in range(rate * 3):
        seconds = index / rate
        if 0.30 <= seconds < 1.10:
            value = 0.35 * math.sin(2 * math.pi * 110 * seconds)
        elif 1.18 <= seconds < 2.00:
            value = 0.30 * math.sin(2 * math.pi * 146.83 * seconds)
        else:
            value = 0.0
        samples.append(struct.pack("<h", int(value * 32767)))
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"".join(samples))


class VirtualSampleExtractorTests(unittest.TestCase):
    def test_requires_guitar_filter_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "riff.wav"
            write_test_wav(source)
            with self.assertRaises(ValueError):
                analyze_long_wav(source)

    def test_finds_virtual_regions_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "riff.wav"
            write_test_wav(source)
            before = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            report = analyze_long_wav(source, guitar_source_confirmed=True)
            after = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            self.assertEqual(before, after)
            self.assertFalse(report["audio_copied"])
            self.assertFalse(report["audio_modified"])
            self.assertGreaterEqual(report["candidate_count"], 2)
            for item in report["candidates"]:
                self.assertLess(item["source_start_sample"], item["source_end_sample"])
                self.assertEqual(len(item["acoustic_fingerprint"]), 64)
                self.assertEqual(item["review_status"], "NEEDS_MUSICAL_REVIEW")

    def test_writes_sidecars_only_to_import_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "riff.wav"
            write_test_wav(source)
            import_root = root / "Import Sample Guitar"
            import_root.mkdir()
            report = analyze_long_wav(source, guitar_source_confirmed=True)
            files = write_virtual_index(report, import_root)
            self.assertGreaterEqual(len(files), 2)
            self.assertTrue(all(path.parent.name == "RIFF_CANDIDATES" for path in files))
            record = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(record["asset_kind"], "VIRTUAL_AUDIO_RANGE")
            self.assertEqual(record["source_sha256"], report["source_sha256"])
            with self.assertRaises(FileExistsError):
                write_virtual_index(report, import_root)

    def test_refuses_wrong_destination_and_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "riff.wav"
            write_test_wav(source)
            report = analyze_long_wav(source, guitar_source_confirmed=True)
            with self.assertRaises(ValueError):
                write_virtual_index(report, root / "FACTORY")
            with source.open("ab") as stream:
                stream.write(b"changed")
            import_root = root / "Import Sample Guitar"
            import_root.mkdir()
            with self.assertRaises(RuntimeError):
                write_virtual_index(report, import_root)


if __name__ == "__main__":
    unittest.main()

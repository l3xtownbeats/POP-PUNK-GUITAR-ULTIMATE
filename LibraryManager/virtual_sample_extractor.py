#!/usr/bin/env python3
"""Virtual riff extraction: index useful WAV ranges without slicing audio.

The source WAV is read-only. The engine writes JSON sidecars under the
user-approved Samples/Import Sample Guitar area; playback resolves each range
against the original file and verifies its SHA-256 before use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import wave
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
DEFAULT_WINDOW_MS = 20
DEFAULT_HOP_MS = 10


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _frame_levels(source: Path, window_ms: int, hop_ms: int) -> tuple[list[dict[str, float]], dict[str, int]]:
    with wave.open(str(source), "rb") as reader:
        if reader.getcomptype() != "NONE":
            raise ValueError("Only uncompressed PCM WAV is supported")
        channels, width, rate, total = (reader.getnchannels(), reader.getsampwidth(),
                                        reader.getframerate(), reader.getnframes())
        if width not in (1, 2, 3, 4) or channels < 1 or rate <= 0:
            raise ValueError("Unsupported WAV format")
        window = max(1, round(rate * window_ms / 1000))
        hop = max(1, round(rate * hop_ms / 1000))
        if total < window:
            raise ValueError("WAV is shorter than one analysis window")
        # Decode each PCM frame to a normalized mono value. Read sequentially;
        # memory use is bounded by one analysis window plus the compact envelope.
        frame_bytes = channels * width
        raw = reader.readframes(total)
        if len(raw) != total * frame_bytes:
            raise IOError("Incomplete PCM source read")
        mono: list[float] = []
        for offset in range(0, len(raw), frame_bytes):
            values = []
            for channel in range(channels):
                start = offset + channel * width
                sample = raw[start:start + width]
                if width == 1:
                    value = (sample[0] - 128) / 128.0
                else:
                    if width == 3:
                        sample += b"\\xff" if sample[2] & 0x80 else b"\\x00"
                    value = int.from_bytes(sample, "little", signed=True) / float(1 << (8 * width - 1))
                values.append(value)
            mono.append(sum(values) / channels)

    levels = []
    for start in range(0, total - window + 1, hop):
        chunk = mono[start:start + window]
        rms = math.sqrt(sum(value * value for value in chunk) / len(chunk))
        crossings = sum((a < 0) != (b < 0) for a, b in zip(chunk, chunk[1:]))
        levels.append({
            "start_sample": start,
            "end_sample": start + window,
            "rms": rms,
            "zcr": crossings / max(1, len(chunk) - 1),
        })
    return levels, {"sample_rate": rate, "channels": channels,
                    "sample_width_bytes": width, "total_frames": total}


def detect_active_ranges(levels: list[dict[str, float]], *, sample_rate: int,
                         total_frames: int, min_duration_ms: int = 250,
                         silence_bridge_ms: int = 180,
                         threshold_floor: float = 0.003) -> list[tuple[int, int]]:
    """Find broad sound-active regions; these are review candidates, not riffs."""
    if not levels:
        return []
    if min_duration_ms < 50 or silence_bridge_ms < 0 or threshold_floor < 0:
        raise ValueError("Invalid segmentation parameters")
    values = [item["rms"] for item in levels]
    noise_floor = statistics.median(sorted(values)[:max(1, len(values) // 5)])
    peak = max(values)
    threshold = max(threshold_floor, noise_floor * 2.8, peak * 0.035)
    active = [item["rms"] >= threshold for item in levels]
    bridge = max(0, round(silence_bridge_ms / DEFAULT_HOP_MS))
    if bridge:
        index = 0
        while index < len(active):
            if active[index]:
                index += 1
                continue
            start = index
            while index < len(active) and not active[index]:
                index += 1
            if start > 0 and index < len(active) and index - start <= bridge:
                active[start:index] = [True] * (index - start)

    ranges = []
    start_index = None
    for index, is_active in enumerate(active + [False]):
        if is_active and start_index is None:
            start_index = index
        elif not is_active and start_index is not None:
            start = levels[start_index]["start_sample"]
            end = min(total_frames, levels[index - 1]["end_sample"])
            if (end - start) * 1000 / sample_rate >= min_duration_ms:
                ranges.append((max(0, start), end))
            start_index = None
    return ranges


def _range_fingerprint(levels: list[dict[str, float]], start: int, end: int) -> str:
    selected = [item for item in levels
                if item["start_sample"] < end and item["end_sample"] > start]
    if not selected:
        return hashlib.sha256(b"empty-range").hexdigest()
    # Quantized RMS + zero-crossing envelope is a repeatable search fingerprint,
    # not an audio reconstruction and not a cryptographic identity of the clip.
    payload = "|".join(
        f'{round(item["rms"] * 10000)}:{round(item["zcr"] * 1000)}'
        for item in selected
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest().upper()


def analyze_long_wav(source: Path, *, guitar_source_confirmed: bool = False,
                     window_ms: int = DEFAULT_WINDOW_MS,
                     hop_ms: int = DEFAULT_HOP_MS,
                     min_duration_ms: int = 250,
                     silence_bridge_ms: int = 180) -> dict[str, Any]:
    source = Path(source).resolve()
    if not guitar_source_confirmed:
        raise ValueError("Confirm that the source has passed guitar-only filtering before analysis")
    if window_ms < 10 or hop_ms < 5 or hop_ms > window_ms:
        raise ValueError("Require window_ms >= 10 and 5 <= hop_ms <= window_ms")
    # Segmentation currently uses a fixed 10 ms hop for gap bridging.
    if hop_ms != DEFAULT_HOP_MS:
        raise ValueError("This version currently requires hop_ms=10")
    levels, fmt = _frame_levels(source, window_ms, hop_ms)
    ranges = detect_active_ranges(levels, sample_rate=fmt["sample_rate"],
                                  total_frames=fmt["total_frames"],
                                  min_duration_ms=min_duration_ms,
                                  silence_bridge_ms=silence_bridge_ms)
    source_hash = sha256_file(source)
    candidates = []
    for start, end in ranges:
        identity = hashlib.sha256(
            f"{source_hash}:{start}:{end}:{VERSION}".encode("ascii")
        ).hexdigest().upper()[:24]
        candidates.append({
            "candidate_id": identity,
            "candidate_type": "SOUND_ACTIVE_REGION",
            "source_start_sample": start,
            "source_end_sample": end,
            "start_seconds": round(start / fmt["sample_rate"], 6),
            "end_seconds": round(end / fmt["sample_rate"], 6),
            "duration_seconds": round((end - start) / fmt["sample_rate"], 6),
            "acoustic_fingerprint": _range_fingerprint(levels, start, end),
            "fingerprint_algorithm": "RMS_ZCR_ENVELOPE_SHA256",
            "fingerprint_version": VERSION,
            "review_status": "NEEDS_MUSICAL_REVIEW",
            "license_status": "UNREVIEWED",
            "proposed_group": "RIFF_CANDIDATES",
        })
    return {
        "schema_version": 1,
        "engine": "VIRTUAL_SAMPLE_EXTRACTION",
        "engine_version": VERSION,
        "source_path": str(source),
        "source_sha256": source_hash,
        **fmt,
        "candidate_count": len(candidates),
        "audio_copied": False,
        "audio_modified": False,
        "candidates": candidates,
        "limitations": [
            "This pass finds broad sound-active regions, not verified riffs, notes, chords, bars or loops.",
            "A guitar-only source must be confirmed by the upstream instrument filter; Piano, Bell and Drum must not enter this stage.",
            "The fingerprint is a compact envelope search key, not a playable sound or proof of identical audio.",
            "Playback requires the original WAV to remain available and its SHA-256 to match.",
            "Candidates remain in Import Sample Guitar for listening and review; nothing is promoted to FACTORY automatically."
        ],
    }


def write_virtual_index(report: dict[str, Any], import_root: Path) -> list[Path]:
    """Write non-destructive JSON sidecars under Samples/Import Sample Guitar."""
    root = Path(import_root).resolve()
    if root.name.casefold() != "import sample guitar":
        raise ValueError("Index destination must be the approved 'Import Sample Guitar' folder")
    source = Path(report["source_path"]).resolve()
    if sha256_file(source) != report["source_sha256"]:
        raise RuntimeError("Source SHA-256 changed after analysis; refusing to index")
    target = root / "VIRTUAL_CANDIDATES" / "RIFF_CANDIDATES"
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for candidate in report["candidates"]:
        path = target / f'{candidate["candidate_id"]}.json'
        record = {
            "schema_version": report["schema_version"],
            "asset_kind": "VIRTUAL_AUDIO_RANGE",
            "source_path": report["source_path"],
            "source_sha256": report["source_sha256"],
            "sample_rate": report["sample_rate"],
            "channels": report["channels"],
            "sample_width_bytes": report["sample_width_bytes"],
            "frame_count": candidate["source_end_sample"] - candidate["source_start_sample"],
            **candidate,
            "playback": "Read source_path from source_start_sample for frame_count frames",
            "automatic_destructive_action": "NONE",
        }
        # Exclusive creation: never overwrite a previous candidate.
        with path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
        written.append(path)
    if sha256_file(source) != report["source_sha256"]:
        raise RuntimeError("Source SHA-256 changed while writing virtual index")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Index useful ranges in a guitar WAV without slicing the audio.")
    parser.add_argument("wav", type=Path)
    parser.add_argument("--import-root", type=Path,
                        help="Samples/Import Sample Guitar; writes JSON virtual candidates")
    parser.add_argument("--guitar-source-confirmed", action="store_true",
                        help="Confirm upstream filtering has excluded Piano, Bell and Drum")
    args = parser.parse_args()
    report = analyze_long_wav(args.wav, guitar_source_confirmed=args.guitar_source_confirmed)
    if args.import_root:
        report["index_files"] = [str(path) for path in write_virtual_index(report, args.import_root)]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

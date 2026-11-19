#!/usr/bin/env python3
"""Prepare physical Sample Mode notes and Melody Mode phrase candidates.

This is deliberately conservative: pitch events are candidate note boundaries,
not guaranteed guitar-note truth. Outputs are new PCM WAV files under staging;
original sources are never modified and every asset remains review/license gated.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from audio_segmenter import STAGING_BASE, _safe_staging_root, propose_segments
from audio_range_io import audio_source_info, write_pcm_wav_range

VERSION = "0.1.0"


def _identity(source_hash: str, mode: str, start: int, end: int) -> str:
    return hashlib.sha256(
        f"{source_hash}:{mode}:{start}:{end}:{VERSION}".encode("utf-8")
    ).hexdigest()[:24].upper()


def _write_clip(source: Path, start: int, end: int,
                destination: Path, expected_rate: int) -> dict[str, Any]:
    return write_pcm_wav_range(
        source, start, end, destination, expected_rate=expected_rate,
    )


def prepare_sample_and_melody(
    source: Path,
    staging_root: Path = STAGING_BASE,
    *,
    max_note_events: int = 500,
    melody_gap_seconds: float = 0.45,
    melody_min_notes: int = 3,
    pre_roll_ms: int = 35,
    post_roll_ms: int = 220,
    pitch_candidates: list[dict[str, Any]] | None = None,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Extract note-event WAVs and grouped melody-phrase WAV candidates."""
    if melody_gap_seconds < 0 or melody_min_notes < 2 or max_note_events < 1:
        raise ValueError("Invalid Sample/Melody extraction limits")
    root = _safe_staging_root(staging_root)
    source = Path(source).resolve()
    source_info = audio_source_info(source)
    rate = source_info.framerate
    total_frames = source_info.frames

    if pitch_candidates is None:
        report = propose_segments(
            source, pre_roll_ms=pre_roll_ms, post_roll_ms=post_roll_ms,
            max_segments=max_note_events,
        )
        source_hash = str(report["source_sha256"]).upper()
        if source_info.framerate != int(report["sample_rate"]):
            raise RuntimeError("Source sample rate changed since Sample/Melody analysis")
        events = report["segments"]
    else:
        source_hash = str(expected_source_sha256 or _sha256(source)).upper()
        pre_roll = round(rate * pre_roll_ms / 1000)
        post_roll = round(rate * post_roll_ms / 1000)
        events = []
        ordered_candidates = sorted(
            pitch_candidates,
            key=lambda item: float(item.get("start_seconds", 0.0)),
        )
        for candidate in ordered_candidates[:max_note_events]:
            note_start = float(candidate.get("start_seconds", 0.0))
            note_end = float(candidate.get("end_seconds", 0.0))
            if note_start < 0 or note_end <= note_start:
                continue
            raw_start = round(note_start * rate)
            raw_end = round(note_end * rate)
            start = max(0, raw_start - pre_roll)
            end = min(total_frames, raw_end + post_roll)
            if end <= start:
                continue
            events.append({
                "source_start_sample": start,
                "source_end_sample": end,
                "detected_note_start_seconds": note_start,
                "detected_note_end_seconds": note_end,
                "midi_note_candidate": candidate.get("midi_note_candidate"),
                "note_name_candidate": candidate.get("note_name_candidate"),
                "confidence": candidate.get("confidence"),
            })
    if _sha256(source) != source_hash:
        raise RuntimeError("Source SHA-256 changed since Sample/Melody analysis")
    clips_dir, manifests_dir = root / "clips", root / "manifests"
    for folder in (clips_dir, manifests_dir):
        folder.mkdir(parents=True, exist_ok=True)
        folder.resolve().relative_to(root)
        folder.resolve().relative_to(STAGING_BASE)

    source_info = audio_source_info(source)
    if source_info.framerate != int(report["sample_rate"]):
        raise RuntimeError("Source sample rate changed since Sample/Melody analysis")
    rate = source_info.framerate
    total_frames = source_info.frames
    events = report["segments"]
    # Group sequential pitch events into phrase candidates. A fixed gap is only
    # a segmentation heuristic; it does not assert a bar, riff or song section.
    groups: list[list[dict[str, Any]]] = []
    for event in events:
        if not groups:
            groups.append([event])
            continue
        previous = groups[-1][-1]
        gap = event["detected_note_start_seconds"] - previous["detected_note_end_seconds"]
        if gap <= melody_gap_seconds:
            groups[-1].append(event)
        else:
            groups.append([event])

    results: dict[str, list[dict[str, Any]]] = {"sample_mode": [], "melody_mode": []}
    created: list[Path] = []
    try:
        for event in events:
            start, end = int(event["source_start_sample"]), int(event["source_end_sample"])
            if start < 0 or end <= start or end > total_frames:
                continue
            asset_id = _identity(source_hash, "SAMPLE_NOTE", start, end)
            clip = clips_dir / f"SAMPLE-{asset_id}.wav"
            manifest = manifests_dir / f"SAMPLE-{asset_id}.json"
            clip_info = _write_clip(source, start, end, clip, rate)
            created.append(clip)
            record = _record(
                asset_id, source, source_hash, clip, manifest, source_info, clip_info, start, end,
                "sample_note_candidate", ["SAMPLE_MODE", "KEYBOARD_PLAYBACK"],
                {"midi_note_candidate": event.get("midi_note_candidate"),
                 "note_name_candidate": event.get("note_name_candidate"),
                 "detected_note_start_seconds": event.get("detected_note_start_seconds"),
                 "detected_note_end_seconds": event.get("detected_note_end_seconds"),
                 "confidence": event.get("confidence")},
            )
            _write_manifest(manifest, record)
            created.append(manifest)
            results["sample_mode"].append(record)

        for group in groups:
            if len(group) < melody_min_notes:
                continue
            start = min(int(x["source_start_sample"]) for x in group)
            end = max(int(x["source_end_sample"]) for x in group)
            if start < 0 or end <= start or end > total_frames:
                continue
            asset_id = _identity(source_hash, "MELODY_PHRASE", start, end)
            clip = clips_dir / f"MELODY-{asset_id}.wav"
            manifest = manifests_dir / f"MELODY-{asset_id}.json"
            clip_info = _write_clip(source, start, end, clip, rate)
            created.append(clip)
            record = _record(
                asset_id, source, source_hash, clip, manifest, source_info, clip_info, start, end,
                "melody_phrase_candidate", ["MELODY_MODE", "MELODY_INSTRUMENT"],
                {"note_event_count": len(group),
                 "note_candidates": [
                     {"midi": x.get("midi_note_candidate"),
                      "name": x.get("note_name_candidate"),
                      "start_seconds": x.get("detected_note_start_seconds"),
                      "end_seconds": x.get("detected_note_end_seconds")}
                     for x in group
                 ],
                 "boundary_basis": "grouped_pitch_event_candidates",
                 "grouping_gap_seconds": melody_gap_seconds},
            )
            _write_manifest(manifest, record)
            created.append(manifest)
            results["melody_mode"].append(record)

        if _sha256(source) != source_hash:
            raise RuntimeError("Source changed during Sample/Melody extraction")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    return {
        "pipeline_version": VERSION,
        "source_path": str(source),
        "source_sha256": source_hash,
        "sample_mode_count": len(results["sample_mode"]),
        "melody_mode_count": len(results["melody_mode"]),
        **results,
        "review_status": "NEEDS_MUSICAL_REVIEW",
        "license_status": "UNREVIEWED",
        "source_modified": False,
        "limitations": [
            "Pitch-event detection is monophonic and may miss chords or overlapping guitar notes.",
            "Melody phrases are grouped by a time-gap heuristic, not verified musical bars or phrases.",
            "Velocity layers, articulation labels, chord recognition and tuning require separate analysis/review.",
            "No candidate is eligible for FACTORY until musical review and explicit license approval."
        ],
    }


def _record(asset_id: str, source: Path, source_hash: str, clip: Path,
            manifest: Path, source_info: Any, clip_info: dict[str, Any],
            start: int, end: int, kind: str,
            targets: list[str], metadata: dict[str, Any]) -> dict[str, Any]:
    rate = int(clip_info["sample_rate"])
    return {
        "schema_version": 1,
        "asset_id": asset_id,
        "parent_asset_id": source_hash,
        "source_path": str(source),
        "source_sha256": source_hash,
        "source_start_sample": start,
        "source_end_sample": end,
        "source_start_seconds": round(start / rate, 6),
        "source_end_seconds": round(end / rate, 6),
        "duration_seconds": round((end - start) / rate, 6),
        "frame_count": end - start,
        "sample_rate": rate,
        "channels": clip_info["channels"],
        "sample_width_bytes": clip_info["sample_width_bytes"],
        "source_format": source_info.source_format,
        "source_subtype": source_info.source_subtype,
        "derived_format": clip_info["derived_format"],
        "derived_subtype": clip_info["derived_subtype"],
        "derived_path": str(clip),
        "derived_sha256": _sha256(clip),
        "kind": kind,
        "engine_targets": targets,
        "musical_metadata": metadata,
        "review_status": "NEEDS_MUSICAL_REVIEW",
        "license_status": "UNREVIEWED",
        "extractor": "sample_melody_pipeline",
        "extractor_version": VERSION,
        "automatic_destructive_action": "NONE",
    }


def _write_manifest(path: Path, record: dict[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()

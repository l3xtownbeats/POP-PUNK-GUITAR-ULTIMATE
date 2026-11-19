#!/usr/bin/env python3
"""Non-destructive finalization audit for the POP PUNK GUITAR staging library."""
from __future__ import annotations

import csv
import hashlib
import json
import wave
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory_curator import INSTRUMENTS, ROLES, STYLES, TONES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def finalize_staging(
    staging_root: Path,
    *,
    reports_root: Path | None = None,
    progress=None,
    cancel_event=None,
) -> dict[str, Any]:
    """Verify every staged manifest and report readiness without moving/copying files."""
    staging = Path(staging_root).resolve()
    if not staging.is_dir():
        raise FileNotFoundError(f"Staging directory not found: {staging}")
    manifests_dir = staging / "manifests"
    manifests = sorted(manifests_dir.glob("*.json")) if manifests_dir.is_dir() else []
    report_base = Path(reports_root or (staging.parent / "reports")).resolve()
    report_base.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir = report_base / f"finalization_{run_id}"
    report_dir.mkdir(parents=True, exist_ok=False)

    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    for index, manifest_path in enumerate(manifests, 1):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Finalization audit cancelled; no staged assets were changed.")
        if progress and (index == 1 or index % 25 == 0 or index == len(manifests)):
            progress(f"Финализация: проверено манифестов {index}/{len(manifests)}")
        row: dict[str, Any] = {
            "manifest_path": str(manifest_path),
            "asset_id": "",
            "derived_path": "",
            "status": "INVALID",
            "review_status": "",
            "license_status": "",
            "style_family": "",
            "instrument_family": "",
            "asset_role": "",
            "tone_family": "",
            "format_family": "",
            "error": "",
        }
        try:
            record = json.loads(manifest_path.read_text(encoding="utf-8"))
            row["asset_id"] = record.get("asset_id", "")
            row["review_status"] = record.get("review_status", "")
            row["license_status"] = record.get("license_status", "")
            derived = Path(record.get("derived_path", ""))
            if not derived.is_absolute():
                derived = (manifest_path.parent / derived).resolve()
            row["derived_path"] = str(derived)
            if not _inside(derived, staging) or not derived.is_file():
                raise ValueError("Derived WAV missing or outside staging")
            if derived.suffix.lower() not in {".wav", ".wave"}:
                raise ValueError("Only WAV assets can be finalized")
            expected_derived = str(record.get("derived_sha256", "")).upper()
            if not expected_derived or _sha256(derived) != expected_derived:
                raise ValueError("Derived WAV SHA-256 mismatch")
            source = Path(record.get("source_path", ""))
            expected_source = str(record.get("source_sha256", "")).upper()
            if not source.is_file() or not expected_source or _sha256(source) != expected_source:
                raise ValueError("Original source missing or SHA-256 mismatch")
            start = int(record.get("source_start_sample", -1))
            end = int(record.get("source_end_sample", -1))
            if start < 0 or end <= start:
                raise ValueError("Invalid source sample boundaries")
            with wave.open(str(derived), "rb") as audio:
                if audio.getcomptype() != "NONE" or audio.getnframes() != end - start:
                    raise ValueError("WAV frame count/PCM validation failed")
            tags = record.get("musical_metadata") or {}
            if not isinstance(tags, dict):
                raise ValueError("musical_metadata must be an object")
            for field, allowed in (
                ("style_family", STYLES),
                ("instrument_family", INSTRUMENTS),
                ("asset_role", ROLES),
                ("tone_family", TONES),
            ):
                value = tags.get(field)
                if value not in allowed:
                    raise ValueError(f"Missing or invalid reviewed tag: {field}")
                row[field] = value
            row["format_family"] = "WAV"
            style_counts[row["style_family"]] += 1
            if row["review_status"] == "REVIEWED" and row["license_status"] == "LICENSE_APPROVED":
                row["status"] = "FACTORY_READY"
            elif row["review_status"] != "REVIEWED":
                row["status"] = "MUSICAL_REVIEW_REQUIRED"
            else:
                row["status"] = "LICENSE_REVIEW_REQUIRED"
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            if row["status"] == "INVALID" and row["review_status"] == "REVIEWED" and row["license_status"] != "LICENSE_APPROVED":
                row["status"] = "LICENSE_REVIEW_REQUIRED"
        status_counts[row["status"]] += 1
        rows.append(row)

    csv_path = report_dir / "finalization_inventory.csv"
    fields = [
        "manifest_path", "asset_id", "derived_path", "status", "review_status",
        "license_status", "style_family", "instrument_family", "asset_role",
        "tone_family", "format_family", "error",
    ]
    with csv_path.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    ready = status_counts["FACTORY_READY"]
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "staging_root": str(staging),
        "report_directory": str(report_dir),
        "manifests_checked": len(manifests),
        "factory_ready_count": ready,
        "musical_review_required_count": status_counts["MUSICAL_REVIEW_REQUIRED"],
        "license_review_required_count": status_counts["LICENSE_REVIEW_REQUIRED"],
        "invalid_count": status_counts["INVALID"],
        "status_counts": dict(status_counts),
        "style_counts_factory_ready": dict(style_counts),
        "factory_distribution_allowed": ready > 0,
        "distribution_executed": False,
        "source_files_modified": False,
        "staged_files_modified": False,
    }
    (report_dir / "finalization_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
    )
    return summary

#!/usr/bin/env python3
"""Explicit human review and license approval for staged WAV candidates."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory_curator import INSTRUMENTS, ROLES, STYLES, TONES
from audio_range_io import audio_source_info


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


def review_manifest(
    manifest_path: Path,
    staging_root: Path,
    *,
    style_family: str,
    instrument_family: str,
    asset_role: str,
    tone_family: str,
    musical_review_notes: str,
    license_evidence: str,
    approve_musical_review: bool = False,
    approve_license: bool = False,
) -> dict[str, Any]:
    """Validate provenance and atomically record explicit human approvals."""
    manifest_path = Path(manifest_path).resolve()
    staging_root = Path(staging_root).resolve()
    if not _inside(manifest_path, staging_root) or not manifest_path.is_file():
        raise ValueError("Manifest must be an existing file inside LibraryManager/staging")
    if not approve_musical_review:
        raise ValueError("Musical review approval must be explicitly confirmed")
    if not approve_license:
        raise ValueError("License approval must be explicitly confirmed")
    if style_family not in STYLES:
        raise ValueError(f"style_family must be one of: {', '.join(sorted(STYLES))}")
    if instrument_family not in INSTRUMENTS:
        raise ValueError(f"instrument_family must be one of: {', '.join(sorted(INSTRUMENTS))}")
    if asset_role not in ROLES:
        raise ValueError(f"asset_role must be one of: {', '.join(sorted(ROLES))}")
    if tone_family not in TONES:
        raise ValueError(f"tone_family must be one of: {', '.join(sorted(TONES))}")
    if not musical_review_notes.strip():
        raise ValueError("Enter a short note describing what was musically checked")
    if not license_evidence.strip():
        raise ValueError("License approval requires a source, license name or evidence note")

    record = json.loads(manifest_path.read_text(encoding="utf-8"))
    derived = Path(record.get("derived_path", ""))
    if not derived.is_absolute():
        derived = (manifest_path.parent / derived).resolve()
    if not _inside(derived, staging_root) or not derived.is_file():
        raise ValueError("Derived WAV must exist inside LibraryManager/staging")
    if derived.suffix.lower() not in {".wav", ".wave"}:
        raise ValueError("Only WAV candidates can be reviewed for FACTORY")
    expected_derived = str(record.get("derived_sha256", "")).upper()
    if not expected_derived or _sha256(derived) != expected_derived:
        raise ValueError("Derived WAV hash does not match manifest")

    source = Path(record.get("source_path", ""))
    expected_source = str(record.get("source_sha256", "")).upper()
    if not source.is_file() or not expected_source or _sha256(source) != expected_source:
        raise ValueError("Original source is missing or its SHA-256 changed")
    start = int(record.get("source_start_sample", -1))
    end = int(record.get("source_end_sample", -1))
    if start < 0 or end <= start:
        raise ValueError("Invalid source sample boundaries")
    original_info = audio_source_info(source)
    derived_info = audio_source_info(derived)
    if end > original_info.frames:
        raise ValueError("Source sample boundaries exceed the original audio")
    if derived_info.frames != end - start:
        raise ValueError("Derived WAV frame count does not match source boundaries")
    if derived_info.source_format.upper() != "WAV" or derived_info.source_subtype not in {"PCM_16", "PCM_24", "PCM_32", "PCM_U8", "PCM"}:
        raise ValueError("Derived asset must be uncompressed PCM WAV")
    if derived_info.framerate != original_info.framerate:
        raise ValueError("Derived WAV sample rate differs from original source")

    metadata = record.setdefault("musical_metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("musical_metadata must be a JSON object")
    metadata.update({
        "style_family": style_family,
        "instrument_family": instrument_family,
        "asset_role": asset_role,
        "tone_family": tone_family,
        "format_family": "WAV",
        "musical_review_notes": musical_review_notes.strip(),
        "license_evidence": license_evidence.strip(),
    })
    record["review_status"] = "REVIEWED"
    record["license_status"] = "LICENSE_APPROVED"
    record["reviewed_at_utc"] = datetime.now(timezone.utc).isoformat()
    record["license_approved_at_utc"] = record["reviewed_at_utc"]
    record["review_validation"] = {
        "source_sha256_verified": True,
        "derived_sha256_verified": True,
        "sample_boundaries_verified": True,
        "explicit_musical_approval": True,
        "explicit_license_approval": True,
    }

    fd, temp_name = tempfile.mkstemp(prefix=manifest_path.name + ".", suffix=".tmp",
                                     dir=str(manifest_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\\n") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, manifest_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return {
        "manifest_path": str(manifest_path),
        "asset_id": record.get("asset_id"),
        "review_status": record["review_status"],
        "license_status": record["license_status"],
        "style_family": style_family,
        "derived_sha256": expected_derived,
        "source_sha256": expected_source,
        "factory_eligible": True,
    }

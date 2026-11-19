#!/usr/bin/env python3
"""Unified, non-destructive POP PUNK GUITAR Library Manager entry point.

Combines inventory/SHA-256/WAV metadata/SFZ audit with the existing acoustic,
rhythm, repeated-pattern and optional virtual-range analyzers. Original assets
are read-only. Derived reports live under LibraryManager/reports; virtual
sidecars are opt-in and live under Import Sample Guitar.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any

from audio_analysis import analyse_wav
from asset_classifier import classify_wav
from library_manager import AUDIO_EXT, ARCHIVE_EXT, EXCLUDED_LABEL_RE, sha256_file, wav_info
from pattern_pipeline import build_pattern_report
from sfz_parser import parse_sfz_file
from virtual_sample_extractor import analyze_long_wav, write_virtual_index
from other_audit import audit_other_library

VERSION = "1.8.0"
SUPPORTED = AUDIO_EXT | {".sfz"} | ARCHIVE_EXT


def resolve_samples_root(selected_path: Path) -> Path:
    """Resolve either Samples or Import Sample Guitar to the Samples root.

    Matching is case-insensitive and tolerates trailing whitespace in the
    directory name. The returned path always contains the incoming directory.
    """
    selected = Path(selected_path).expanduser()
    if not selected.exists():
        raise FileNotFoundError(f"Выбранный путь не существует: {selected}")
    if not selected.is_dir():
        raise NotADirectoryError(f"Выбранный путь не является папкой: {selected}")
    selected = selected.resolve()

    def is_incoming(path: Path) -> bool:
        return path.name.strip().casefold() == "import sample guitar"

    if is_incoming(selected):
        samples_root = selected.parent
        incoming = selected
    else:
        samples_root = selected
        try:
            children = [p for p in samples_root.iterdir()
                        if p.is_dir() and is_incoming(p)]
        except OSError as exc:
            raise OSError(f"Не удалось прочитать выбранную папку: {samples_root}: {exc}") from exc
        if not children:
            # Also tolerate a case-insensitive spelling on filesystems where
            # directory lookup itself is case-sensitive.
            raise FileNotFoundError(
                "В выбранной папке не найдена подпапка 'Import Sample Guitar'. "
                f"Выбранный путь: {samples_root}. Выберите Samples либо саму Import Sample Guitar."
            )
        if len(children) > 1:
            raise RuntimeError(
                "Найдено несколько папок Import Sample Guitar. "
                "Выберите непосредственно нужную папку, чтобы избежать анализа не той библиотеки."
            )
        incoming = children[0]

    if not incoming.is_dir():
        raise FileNotFoundError(f"Папка импорта не найдена или недоступна: {incoming}")
    return samples_root


def _is_excluded(path: Path) -> bool:
    return any(EXCLUDED_LABEL_RE.search(part) for part in path.parts)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite report: {path}")
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite report: {path}")
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_manager(samples_root: Path, *, analyze_audio: bool = False,
                guitar_source_confirmed: bool = False,
                write_virtual: bool = False,
                reports_root: Path | None = None) -> dict[str, Any]:
    samples_root = resolve_samples_root(samples_root)
    incoming = next(p for p in samples_root.iterdir()
                    if p.is_dir() and p.name.strip().casefold() == "import sample guitar")
    if write_virtual and not (analyze_audio and guitar_source_confirmed):
        raise ValueError("--write-virtual-index requires --analyze-audio and --guitar-source-confirmed")

    manager_root = Path(__file__).resolve().parent
    report_base = (reports_root or (manager_root / "reports")).expanduser().resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    reports = report_base / f"run_{run_id}"
    reports.mkdir(parents=True, exist_ok=False)

    all_files = sorted(path for path in incoming.rglob("*") if path.is_file())
    excluded = [path for path in all_files if _is_excluded(path.relative_to(incoming))]
    included = [path for path in all_files if not _is_excluded(path.relative_to(incoming))]
    inventory: list[dict[str, Any]] = []
    audio_reports: list[dict[str, Any]] = []
    classification_reports: list[dict[str, Any]] = []
    sfz_rows: list[dict[str, Any]] = []
    duplicate_groups: dict[str, list[str]] = defaultdict(list)
    errors: list[dict[str, str]] = []

    for path in included:
        ext = path.suffix.lower()
        relative = str(path.relative_to(incoming))
        try:
            stat = path.stat()
            digest = sha256_file(path)
            row: dict[str, Any] = {
                "relative_path": relative,
                "filename": path.name,
                "extension": ext,
                "bytes": stat.st_size,
                "sha256": digest,
                "source_path": str(path.resolve()),
                "source_modified_by_manager": False,
            }
            if ext not in SUPPORTED:
                row["category_suggestion"] = "OTHER_REVIEW_REQUIRED"
                row["audio_analysis_status"] = "UNSUPPORTED_FORMAT"
                row["classification_status"] = "MANUAL_REVIEW_REQUIRED"
                row["unsupported_reason"] = "File extension is not currently supported by the analysis pipeline."
            elif ext in AUDIO_EXT:
                meta = wav_info(path)
                row.update(meta)
                row["category_suggestion"] = (
                    "AUDIO_SAMPLE" if meta.get("wav_status") in {"OK", "NON_PCM_OR_EXTENSIBLE"}
                    else "OTHER_REVIEW_REQUIRED"
                )
                if analyze_audio and row.get("wav_status") in {"OK", "NON_PCM_OR_EXTENSIBLE"}:
                    try:
                        acoustic = analyse_wav(path)
                        acoustic["source_sha256"] = digest
                        classification = classify_wav(path, analyze_pitch=True)
                        classification["source_sha256"] = digest
                        classification["classification_status"] = "CANDIDATE_REQUIRES_REVIEW"
                        classification["automatic_factory_promotion"] = False
                        classification_reports.append(classification)
                        pattern = build_pattern_report(acoustic)
                        audio_record: dict[str, Any] = {
                            "source_path": str(path.resolve()),
                            "source_sha256": digest,
                            "acoustic_analysis": acoustic,
                            "pattern_analysis": pattern,
                            "virtual_extraction": None,
                        }
                        if guitar_source_confirmed:
                            virtual = analyze_long_wav(path, guitar_source_confirmed=True)
                            audio_record["virtual_extraction"] = virtual
                            if write_virtual:
                                audio_record["virtual_index_files"] = [
                                    str(p) for p in write_virtual_index(virtual, incoming)
                                ]
                        audio_reports.append(audio_record)
                        row["audio_analysis_status"] = "ANALYZED"
                        row["classification_status"] = "CANDIDATE_REQUIRES_REVIEW"
                        row["asset_kind_candidate"] = classification.get("asset_kind_candidate", "UNKNOWN")
                        row["sample_subtype_candidate"] = classification.get("sample_subtype_candidate", "UNKNOWN")
                        row["classification_confidence"] = classification.get("classification_confidence")
                        row["pattern_candidate_count"] = pattern["pattern_analysis"]["candidate_count"]
                        row["virtual_region_count"] = (
                            audio_record["virtual_extraction"]["candidate_count"]
                            if audio_record["virtual_extraction"] else ""
                        )
                    except Exception as exc:
                        row["audio_analysis_status"] = "ERROR"
                        errors.append({"path": relative, "stage": "AUDIO_ANALYSIS",
                                       "error": f"{type(exc).__name__}: {exc}"})
                elif analyze_audio:
                    row["audio_analysis_status"] = "SKIPPED_INVALID_WAV"
            elif ext == ".sfz":
                row["category_suggestion"] = "SFZ_INSTRUMENT"
            else:
                row["category_suggestion"] = "ARCHIVE_REVIEW_REQUIRED"
            inventory.append(row)
            duplicate_groups[digest].append(relative)
        except Exception as exc:
            errors.append({"path": relative, "stage": "INVENTORY",
                           "error": f"{type(exc).__name__}: {exc}"})

    for sfz in (p for p in included if p.suffix.lower() == ".sfz"):
        try:
            sfz_rows.extend(parse_sfz_file(sfz, incoming))
        except Exception as exc:
            errors.append({"path": str(sfz.relative_to(incoming)), "stage": "SFZ_PARSE",
                           "error": f"{type(exc).__name__}: {exc}"})

    duplicates = [
        {"sha256": digest, "count": len(paths), "paths": paths}
        for digest, paths in sorted(duplicate_groups.items()) if len(paths) > 1
    ]
    other_audit_summary = audit_other_library(samples_root, reports / "other_audit")
    summary = {
        "manager_version": VERSION,
        "run_id": run_id,
        "report_directory": str(reports),
        "samples_root": str(samples_root),
        "incoming_folder": str(incoming),
        "files_scanned": len(inventory),
        "files_excluded_by_piano_bell_drum_path_label": len(excluded),
        "wav_files": sum(row["extension"] in AUDIO_EXT for row in inventory),
        "sfz_files": sum(row["extension"] == ".sfz" for row in inventory),
        "archives_for_manual_review": sum(row["extension"] in ARCHIVE_EXT for row in inventory),
        "exact_duplicate_groups": len(duplicates),
        "sfz_sample_references": len(sfz_rows),
        "sfz_missing_references": sum(row.get("status") == "MISSING" for row in sfz_rows),
        "sfz_outside_library_references": sum(row.get("status") == "OUTSIDE_LIBRARY" for row in sfz_rows),
        "audio_analysis_enabled": analyze_audio,
        "guitar_source_manually_confirmed": guitar_source_confirmed,
        "audio_files_analyzed": len(audio_reports),
        "asset_classifications_created": len(classification_reports),
        "classification_policy": "CANDIDATE_ONLY_REQUIRES_HUMAN_REVIEW",
        "repeated_rhythm_pattern_candidates": sum(
            item["pattern_analysis"]["pattern_analysis"]["candidate_count"] for item in audio_reports
        ),
        "virtual_active_region_candidates": sum(
            item["virtual_extraction"]["candidate_count"]
            for item in audio_reports if item["virtual_extraction"] is not None
        ),
        "errors": len(errors),
        "other_audit": other_audit_summary,
        "unsupported_import_files": sum(row.get("audio_analysis_status") == "UNSUPPORTED_FORMAT" for row in inventory),
        "source_files_modified": False,
        "source_files_moved_or_deleted": False,
        "automatic_factory_promotion": False,
        "note": "Candidates are evidence for review, not confirmed riffs/notes/chords/sections. No source asset is changed."
    }

    _write_csv(reports / "unified_inventory.csv", inventory)
    _write_csv(reports / "unified_sfz_references.csv", sfz_rows)
    _write_json(reports / "unified_exact_duplicates.json", duplicates)
    _write_json(reports / "unified_audio_analysis.json", audio_reports)
    _write_json(reports / "unified_asset_classification.json", classification_reports)
    _write_json(reports / "unified_errors.json", errors)
    _write_json(reports / "unified_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified safe Library Manager: inventory, SFZ audit and optional audio analysis."
    )
    parser.add_argument("--samples", type=Path,
                        default=Path(__file__).resolve().parent.parent / "Samples")
    parser.add_argument("--analyze-audio", action="store_true",
                        help="Run acoustic/rhythm/repeated-pattern analysis on valid WAV files.")
    parser.add_argument("--guitar-source-confirmed", action="store_true",
                        help="Operator confirms that input has already excluded Piano, Bell and Drum.")
    parser.add_argument("--write-virtual-index", action="store_true",
                        help="Write non-audio JSON range sidecars under Import Sample Guitar (never slices WAV).")
    args = parser.parse_args()
    try:
        summary = run_manager(
            args.samples,
            analyze_audio=args.analyze_audio,
            guitar_source_confirmed=args.guitar_source_confirmed,
            write_virtual=args.write_virtual_index,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Reports: {summary['report_directory']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

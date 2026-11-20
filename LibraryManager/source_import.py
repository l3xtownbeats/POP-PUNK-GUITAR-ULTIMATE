#!/usr/bin/env python3
"""Non-destructive source import and provenance registration for Manager 3.0.

The explicit import workflow makes verified copies inside Import Sample Guitar;
original source files are never modified, moved, renamed, overwritten or deleted.
Expensive audio decoding and musical analysis belong to later stages.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

AUDIO_EXTENSIONS = {
    ".wav", ".wave", ".aif", ".aiff", ".flac", ".ogg", ".oga",
    ".mp3", ".m4a", ".aac", ".wma", ".opus",
}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | {".sfz", ".zip", ".7z", ".rar"}
REGISTRY_VERSION = 2


def _identity(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _walk(path: Path, errors: list[dict] | None = None):
    """Yield files recursively without following symlinks; report inaccessible paths."""
    if path.is_file():
        yield path
        return
    stack = [path]
    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                    except OSError as exc:
                        if errors is not None:
                            errors.append({
                                "path": entry.path,
                                "stage": "IMPORT_DIRECTORY_ENTRY",
                                "error": f"{type(exc).__name__}: {exc}",
                            })
        except OSError as exc:
            if errors is not None:
                errors.append({
                    "path": str(folder),
                    "stage": "IMPORT_DIRECTORY_SCAN",
                    "error": f"{type(exc).__name__}: {exc}",
                })


def register_sources(
    selected_paths: Iterable[str | Path],
    registry_path: str | Path,
    *,
    imported_paths: dict[str, str | Path] | None = None,
) -> dict:
    """Register multiple files/folders, retaining exact original paths and hierarchy."""
    selections = [Path(item).expanduser().resolve() for item in selected_paths]
    if not selections:
        raise ValueError("Не выбраны файлы или папки для импорта.")
    for item in selections:
        if not item.exists():
            raise FileNotFoundError(f"Источник не найден: {item}")
        if not (item.is_file() or item.is_dir()):
            raise ValueError(f"Неподдерживаемый тип источника: {item}")

    target = Path(registry_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
        if data.get("registry_version") not in {1, REGISTRY_VERSION}:
            raise ValueError("Неизвестная версия реестра импорта; исходный реестр не изменён.")
        records = data.get("sources", [])
    else:
        records = []

    records_by_identity = {
        record["identity"]: record for record in records if "identity" in record
    }
    known = set(records_by_identity)
    imported_map = {
        _identity(Path(source)): str(Path(destination).expanduser().resolve())
        for source, destination in (imported_paths or {}).items()
    }
    added, duplicates, updated, errors = [], [], [], []
    sfz_roots: dict[str, Path] = {}
    for selected in selections:
        root = selected if selected.is_dir() else selected.parent
        for file_path in _walk(selected, errors):
            try:
                resolved = file_path.resolve()
                stat = resolved.stat()
                identity = _identity(resolved)
                if identity in known:
                    existing = records_by_identity.get(identity)
                    imported_path = imported_map.get(identity)
                    if existing is not None and imported_path:
                        existing["imported_path"] = imported_path
                        existing["import_status"] = "COPIED_AND_VERIFIED"
                        updated.append(existing)
                    duplicates.append(str(resolved))
                    continue
                suffix = resolved.suffix.lower()
                relative = os.path.relpath(resolved, root)
                record = {
                    "identity": identity,
                    "source_path": str(resolved),
                    "selected_root": str(root),
                    "relative_path": relative,
                    "filename": resolved.name,
                    "extension": suffix,
                    "size_bytes": stat.st_size,
                    "modified_ns": stat.st_mtime_ns,
                    "format_group": (
                        "AUDIO" if suffix in AUDIO_EXTENSIONS else
                        "SFZ" if suffix == ".sfz" else
                        "ARCHIVE" if suffix in {".zip", ".7z", ".rar"} else
                        "OTHER_REVIEW_REQUIRED"
                    ),
                    "registration_status": "REGISTERED",
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "source_modified_by_manager": False,
                }
                if identity in imported_map:
                    record["imported_path"] = imported_map[identity]
                    record["import_status"] = "COPIED_AND_VERIFIED"
                records.append(record)
                records_by_identity[identity] = record
                known.add(identity)
                added.append(record)
                if suffix == ".sfz":
                    sfz_roots[identity] = root
            except OSError as exc:
                errors.append({"path": str(file_path), "error": f"{type(exc).__name__}: {exc}"})

    # Re-audit every registered SFZ on each import pass, including duplicate
    # selections, so dependency status never silently goes stale.
    sfz_roots = {
        item["identity"]: Path(item.get("selected_root") or Path(item["source_path"]).parent)
        for item in records
        if str(item.get("extension", "")).lower() == ".sfz"
        and item.get("identity") and item.get("source_path")
    }

    # Resolve SFZ sample= and #include dependencies before the import is
    # considered scan-ready. The parser is read-only and confines samples to
    # the selected library root; unresolved references remain explicit.
    sfz_audit = []
    if sfz_roots:
        # Resolve each SFZ registry record in O(1), rather than rescanning the
        # full registry for every SFZ file (quadratic behavior on large banks).
        records_by_identity = {
            item["identity"]: item for item in records if item.get("identity")
        }
        try:
            from sfz_parser import parse_sfz_file
        except ImportError:
            from .sfz_parser import parse_sfz_file
        for sfz_identity, library_root in sfz_roots.items():
            sfz_record = records_by_identity.get(sfz_identity)
            if sfz_record is None:
                sfz_audit.append({
                    "sfz_identity": sfz_identity,
                    "library_root": str(library_root),
                    "status": "SFZ_REGISTRY_RECORD_MISSING",
                    "error": "Registered SFZ identity is missing from source registry.",
                })
                continue
            try:
                rows = parse_sfz_file(Path(sfz_record["source_path"]), library_root)
                for row in rows:
                    sfz_audit.append({
                        "sfz_identity": sfz_identity,
                        "sfz_path": sfz_record["source_path"],
                        "library_root": str(library_root),
                        **row,
                    })
            except Exception as exc:
                sfz_audit.append({
                    "sfz_identity": sfz_identity,
                    "sfz_path": sfz_record["source_path"],
                    "library_root": str(library_root),
                    "status": "SFZ_AUDIT_ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                })

    payload = {
        "registry_version": REGISTRY_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(records),
        "sources": records,
        "sfz_dependency_audit": sfz_audit,
    }
    fd, temporary_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise

    return {
        "registry_path": str(target),
        "selected_sources": len(selections),
        "registered_files": len(added),
        "already_registered": len(duplicates),
        "registry_records_updated": len(updated),
        "errors": errors,
        "registered_by_format": {
            key: sum(1 for item in added if item["format_group"] == key)
            for key in sorted({item["format_group"] for item in added})
        },
        "sfz_dependency_rows": len(sfz_audit),
        "sfz_dependencies_found": sum(1 for row in sfz_audit if row.get("status") == "FOUND"),
        "sfz_dependencies_blocked": sum(1 for row in sfz_audit if row.get("status") != "FOUND"),
        "source_files_modified": False,
        "source_files_moved": False,
        "source_files_deleted": False,
        "next_stage": "SCAN_LIBRARY",
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _safe_folder_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" ._")
    return cleaned[:80] or "Source"


def _copy_verified(
    source: Path,
    destination: Path,
    *,
    cancel_event=None,
    progress=None,
) -> tuple[str, int]:
    """Copy one source without modifying it; verify the completed destination hash."""
    import hashlib

    digest = hashlib.sha256()
    size = 0
    source_before = source.stat()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("IMPORT GUITAR остановлен пользователем.")
            block = src.read(1024 * 1024)
            if not block:
                break
            dst.write(block)
            digest.update(block)
            size += len(block)
            if progress and (size % (16 * 1024 * 1024) < len(block)):
                progress(f"Копирование: {source.name} — {size:,} байт…")
        dst.flush()
        os.fsync(dst.fileno())
    source_digest = digest.hexdigest().upper()
    source_after = source.stat()
    if (
        size != source_before.st_size
        or source_after.st_size != source_before.st_size
        or source_after.st_mtime_ns != source_before.st_mtime_ns
    ):
        raise IOError(f"Исходный файл изменился во время импорта: {source}")
    try:
        os.utime(
            destination,
            ns=(source_after.st_atime_ns, source_after.st_mtime_ns),
        )
    except OSError:
        pass
    destination_digest = _sha256(destination)
    if destination_digest != source_digest:
        raise IOError(f"SHA-256 копии не совпадает с оригиналом: {source}")
    return source_digest, size


def import_sources_to_library(
    selected_paths: Iterable[str | Path],
    incoming_root: str | Path,
    registry_path: str | Path,
    *,
    progress=None,
    cancel_event=None,
) -> dict:
    """Copy selected libraries into Import Sample Guitar, verify and register provenance.

    The original source paths are read-only. Every batch is first copied into a
    hidden temporary directory inside the incoming library, verified file by
    file, then atomically renamed into place. If any step fails, this batch is
    rolled back and the original sources remain untouched.
    """
    selections = [Path(item).expanduser().resolve() for item in selected_paths]
    if not selections:
        raise ValueError("Не выбраны файлы или папки для импорта.")
    incoming = Path(incoming_root).expanduser().resolve()
    if not incoming.is_dir():
        raise NotADirectoryError(f"Папка Import Sample Guitar не найдена: {incoming}")
    for item in selections:
        if not item.exists() or not (item.is_file() or item.is_dir()):
            raise FileNotFoundError(f"Источник не найден или не поддерживается: {item}")
        if item.is_dir():
            try:
                incoming.relative_to(item)
            except ValueError:
                pass
            else:
                if item != incoming:
                    raise ValueError(
                        f"Нельзя импортировать папку-родитель самой Import Sample Guitar: {item}"
                    )

    registry = Path(registry_path).expanduser().resolve()
    existing_records = {}
    if registry.exists():
        data = json.loads(registry.read_text(encoding="utf-8"))
        if data.get("registry_version") not in {1, REGISTRY_VERSION}:
            raise ValueError("Неизвестная версия реестра импорта; оригинальные данные не изменены.")
        existing_records = {
            item.get("identity"): item for item in data.get("sources", [])
            if item.get("identity")
        }

    token = uuid.uuid4().hex
    temporary_root = incoming / f".manager-import-tmp-{token}"
    final_root = incoming / (
        "IMPORT_BATCH_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + token[:8]
    )
    copied_files = 0
    copied_bytes = 0
    errors = []
    imported_paths: dict[str, Path] = {}
    seen_sources: set[str] = set()
    has_new_copy = False

    # Individual files selected from the same library retain their common
    # relative directory tree. This keeps SFZ sample= and #include references
    # resolvable when the user selects an SFZ and its samples as separate files.
    all_selected_directories = [item for item in selections if item.is_dir()]
    selected_directories = [
        item for item in all_selected_directories
        if not any(parent in item.parents for parent in all_selected_directories if parent != item)
    ]
    file_groups: dict[str, list[Path]] = {}
    for item in selections:
        if not item.is_file():
            continue
        if any(
            item == directory or directory in item.parents
            for directory in selected_directories
        ):
            continue
        drive_key = item.drive.casefold()
        file_groups.setdefault(drive_key, []).append(item)

    file_plan: dict[str, tuple[Path, Path]] = {}
    for group in file_groups.values():
        common = Path(os.path.commonpath([str(item.parent) for item in group])).resolve()
        group_key = hashlib.sha256(str(common).encode("utf-8")).hexdigest()[:10]
        destination_base = temporary_root / "Selected_Files" / group_key
        for item in group:
            file_plan[_identity(item)] = (common, destination_base)

    def reusable_existing(source: Path) -> Path | None:
        record = existing_records.get(_identity(source), {})
        target = Path(record.get("imported_path", "")) if record else Path()
        if not target.is_absolute() or not target.is_file():
            return None
        try:
            stat = source.stat()
            if record.get("size_bytes") == stat.st_size and record.get("modified_ns") == stat.st_mtime_ns:
                return target.resolve()
        except OSError:
            return None
        return None

    try:
        temporary_root.mkdir(parents=False, exist_ok=False)
        for selection_index, selected in enumerate(selections, start=1):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("IMPORT GUITAR остановлен пользователем.")
            root_is_incoming = selected == incoming
            if selected.is_dir():
                if selected not in selected_directories:
                    # A nested directory is already included by a selected parent.
                    continue
                files = list(_walk(selected, errors))
                source_root = selected
                destination_base = temporary_root / "Sources" / (
                    f"{selection_index:03d}_{_safe_folder_name(selected.name)}"
                )
            else:
                if _identity(selected) not in file_plan:
                    # A separately selected file already included by a selected
                    # directory is copied as part of that directory instead.
                    continue
                files = [selected]
                source_root, destination_base = file_plan[_identity(selected)]

            if errors:
                first = errors[0]
                raise OSError(
                    "Не удалось полностью прочитать выбранную папку; импорт отменён без частичной копии: "
                    f"{first.get('path')}: {first.get('error')}"
                )

            for source in files:
                source = source.resolve()
                identity = _identity(source)
                if identity in seen_sources:
                    continue
                seen_sources.add(identity)

                # Files already inside the active import root are scanned in place.
                try:
                    source.relative_to(incoming)
                    already_in_library = True
                except ValueError:
                    already_in_library = False
                if already_in_library:
                    imported_paths[str(source)] = source
                    continue

                reusable = reusable_existing(source)
                if reusable is not None:
                    imported_paths[str(source)] = reusable
                    continue

                relative = source.relative_to(source_root) if selected.is_dir() else Path(source.name)
                destination = destination_base / relative
                digest, size = _copy_verified(
                    source, destination, cancel_event=cancel_event, progress=progress,
                )
                copied_files += 1
                copied_bytes += size
                has_new_copy = True
                # The batch is renamed below; store the final destination now.
                imported_paths[str(source)] = final_root / destination.relative_to(temporary_root)
                if progress:
                    progress(f"Проверена копия: {source.name} — SHA-256 {digest}")

        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("IMPORT GUITAR остановлен пользователем.")
        if has_new_copy:
            os.replace(temporary_root, final_root)
        else:
            temporary_root.rmdir()

        try:
            registry_result = register_sources(
                selections, registry, imported_paths=imported_paths,
            )
        except Exception:
            if has_new_copy:
                shutil.rmtree(final_root, ignore_errors=True)
            raise

        return {
            "imported_library_folder": str(incoming),
            "import_batch": str(final_root) if has_new_copy else None,
            "copied_files": copied_files,
            "copied_bytes": copied_bytes,
            "registry": registry_result,
            "source_files_modified": False,
            "source_files_moved": False,
            "source_files_deleted": False,
            "copy_integrity": "SHA256_VERIFIED",
            "next_stage": "SCAN_LIBRARY",
        }
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise

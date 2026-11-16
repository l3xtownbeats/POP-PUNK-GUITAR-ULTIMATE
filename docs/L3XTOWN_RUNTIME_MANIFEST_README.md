# L3XTOWN Runtime Manifest — Readme

File: `L3XTOWN_RUNTIME_MANIFEST.csv`

## Purpose
Portable per-file source manifest for the 387 user-owned L3XTOWN GUITAR WAV recordings. It consolidates stable file identity from `L3XTOWN_SAMPLE_MAP.csv`, adds a relative path from the L3XTOWN library root, and imports technical fields from `L3XTOWN_INVENTORY.csv` only when the available metadata supports a safe match.

## Current reconciliation
- Total manifest rows: 387.
- Unique inventory matches: 126 (`MATCHED_UNIQUE`).
- Ambiguous source matches with identical technical metadata across every candidate: 149 (`MATCHED_AMBIGUOUS_IDENTICAL_METADATA`). Technical values are safe to copy because every candidate has the same sample rate, channel count, bit depth, duration, and inventory size; the exact source-row identity remains unresolved.
- Ambiguous matches with conflicting technical metadata: 112 (`AMBIGUOUS_METADATA_CONFLICT`). Technical fields remain blank; do not guess.
- Missing inventory matches: 0.
- Sum of source_bytes: 846,265,382 bytes.
- Each sample_id is the first 16 lowercase hexadecimal characters of its source SHA-256.

## Why ambiguity remains
The inventory's Folder column is flattened and omits the full parent guitar-family path. Some leaf-folder + filename pairs therefore match multiple inventory rows. The reconciliation distinguishes harmless ambiguity (all candidate metadata values identical) from conflicting ambiguity (candidate metadata differs).

## How to clear the remaining 112 conflicts
Preferred source correction: regenerate the inventory with a full relative path from the L3XTOWN GUITAR root, e.g. `Гитары - Квинты/01 ENGL/Квинты/filename.wav`, instead of a leaf-folder-only value such as `Квинты`.

Alternative: read each WAV header to obtain sample rate, channels, and bit depth, and measure exact duration from the file itself. Do not assign duration or size from a sibling recording.

## Path convention
`relative_path_from_library_root` is relative to the root folder `L3XTOWN GUITAR`. It uses forward slashes and contains no machine-specific drive letter or absolute PC path. Preserve original filename and source category.

## Immutable source identity
- `source_bytes` and `sha256` come from SAMPLE_MAP.
- Do not edit or overwrite original WAV files.
- If future analysis produces trimmed, normalized, looped, or otherwise processed audio, store it as a separate derived asset with a reference to the original sample_id and SHA-256.

## Status semantics
- `MATCHED_UNIQUE`: exactly one inventory row matched; technical fields copied.
- `MATCHED_AMBIGUOUS_IDENTICAL_METADATA`: multiple candidate inventory rows matched, but every candidate has identical technical fields; technical values copied while source-row identity remains unresolved.
- `AMBIGUOUS_METADATA_CONFLICT`: multiple candidate rows disagree; technical fields intentionally blank.
- `MISSING_INVENTORY_MATCH`: no inventory row matched (none in current manifest).

## Not an audio-analysis result
The manifest contains no measured pitch, tuning, articulation, chord type, tempo, transient, usable-region, loop, or velocity-layer analysis. Those fields must be populated only from actual audio inspection. Filename-derived labels remain provisional.

## Development gate
Creating or reconciling this manifest does not constitute audio-library integration and does not authorize plugin, preset, engine, sound-quality, or final-build testing. The existing gate remains: collect and integrate the required libraries and create/integrate all 500 core factory presets before any such testing.

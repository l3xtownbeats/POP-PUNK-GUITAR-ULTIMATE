# L3XTOWN Runtime Manifest — Readme

File: `L3XTOWN_RUNTIME_MANIFEST.csv`

## Purpose
Portable per-file source manifest for the 387 user-owned L3XTOWN GUITAR WAV recordings. It consolidates stable file identity from `L3XTOWN_SAMPLE_MAP.csv`, adds a relative path from the L3XTOWN library root, and imports technical fields from `L3XTOWN_INVENTORY.csv` only where the folder+filename join is unique.

## Generated record counts
- Total manifest rows: 387.
- Unique inventory matches: 126.
- Ambiguous inventory matches: 261.
- Missing inventory matches: 0.
- Sum of source_bytes: 846,265,382 bytes.
- Every sample_id is the first 16 lowercase hexadecimal characters of its source SHA-256.

## Important join limitation
The inventory's Folder column is flattened and omits the full parent guitar-family path. Therefore, 261 rows have multiple possible inventory matches when joining by leaf folder plus filename. These rows are marked `AMBIGUOUS_FLATTENED_INVENTORY_FOLDER`; their sample-rate, channel, bit-depth, duration, and inventory-size fields are intentionally left blank.

Do not fill these blanks by copying values from a sibling sample or assuming all recordings share identical metadata. Resolve the ambiguous rows from a corrected inventory that preserves the complete relative folder path, or by reading each WAV's actual header and measuring its duration.

## Path convention
`relative_path_from_library_root` is relative to the root folder `L3XTOWN GUITAR`. It uses forward slashes and contains no machine-specific drive letter or absolute PC path. Preserve the original filename and source category.

## Immutable source identity
- `source_bytes` and `sha256` come from SAMPLE_MAP.
- Do not edit or overwrite original WAV files.
- If future analysis produces trimmed, normalized, looped, or otherwise processed audio, store it as a separate derived asset with a reference to the original sample_id and SHA-256.

## Status semantics
- `MATCHED_UNIQUE`: exactly one inventory row matched by leaf folder and filename; technical fields are copied from that row.
- `AMBIGUOUS_FLATTENED_INVENTORY_FOLDER`: multiple inventory rows matched; technical fields are blank pending reliable resolution.
- `MISSING_INVENTORY_MATCH`: no inventory row matched (none found in this generation).

## Not an audio-analysis result
The manifest contains no measured pitch, tuning, articulation, chord type, tempo, transient, usable-region, loop, or velocity-layer analysis. Those fields must be populated only from actual audio inspection. Filename-derived labels remain provisional.

## Development gate
Creating this manifest does not constitute audio-library integration and does not authorize plugin, preset, engine, sound-quality, or final-build testing. The existing gate remains: collect and integrate the required libraries and create/integrate all 500 core factory presets before any such testing.

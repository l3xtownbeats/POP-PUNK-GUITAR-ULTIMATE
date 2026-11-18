# POP PUNK GUITAR LIBRARY MANAGER ULTIMATE

## Safe inventory engine 0.1.0

This first working core is scan-only. It does not move, rename, delete, rewrite, or overwrite source audio.

### Required library layout

Samples/
- FACTORY/
- Import Sample Guitar/
- OTHER/

### Run on Windows

1. Keep this LibraryManager folder inside the project.
2. Confirm the three folders above exist under the single Samples root.
3. Put incoming WAV, SFZ and archive files inside Samples/Import Sample Guitar.
4. Double-click RUN_LIBRARY_MANAGER.bat.

Python 3.10+ is required. The scanner uses only the Python standard library.

### Reports

Reports are written beside the tool in reports/:
- inventory.csv — file inventory, SHA-256, WAV header metadata and conservative filename hints.
- sfz_sample_references.csv — SFZ sample path resolution (FOUND / MISSING / OUTSIDE_LIBRARY).
- exact_duplicates.json — exact SHA-256 duplicate groups; nothing is removed.
- summary.json — scan totals.
- scan_cache.sqlite3 — resumable metadata/hash cache.

### Safety

- Original files are never changed.
- Automatic filename hints are not treated as final musical classification.
- Archives are inventoried only; they are not extracted.
- Unsupported files are skipped, not deleted.
- Copy/sort mode will be a separate future stage with collision checks, a transaction journal and rollback.

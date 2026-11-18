# POP PUNK GUITAR LIBRARY MANAGER ULTIMATE

## Safe inventory engine 0.2.0

This is a read-only inventory and SFZ audit stage. It never moves, renames, deletes, rewrites, or overwrites source audio or SFZ files.

### Required library layout

```
Samples/
├── FACTORY/
├── Import Sample Guitar/
└── OTHER/
``

Keep this as the single approved Samples root. Put new incoming WAV, SFZ and archive files in `Samples/Import Sample Guitar`.

### Run on Windows

1. Keep this LibraryManager folder inside the project.
2. Confirm the three folders above exist under the single Samples root.
3. Put incoming WAV, SFZ and archive files inside `Samples/Import Sample Guitar`.
4. Double-click `RUN_LIBRARY_MANAGER.bat`.

Python 3.10+ is required. The scanner uses only the Python standard library.

### Reports

Reports are written beside the tool in `reports/`:
- `inventory.csv` — file inventory, SHA-256, WAV header metadata and conservative filename hints.
- `sfz_sample_references.csv` — per-region SFZ sample resolution, note/velocity ranges, group label, trigger and loop hints.
- `exact_duplicates.json` — exact SHA-256 duplicate groups; nothing is removed.
- `summary.json` — scan totals and SFZ reference totals.
- `scan_cache.sqlite3` — resumable metadata/hash cache.

### SFZ support in 0.2.0

- Handles multiple regions per SFZ.
- Reads quoted and unquoted opcodes, inline tags and comments.
- Resolves relative sample paths and `control/default_path`.
- Reads `#include` files and reports missing include files and include cycles.
- Applies conservative inherited values from global/master/group scopes.
- Exports lokey/hikey and lovel/hivel ranges plus group_label, trigger, loop_mode and pitch_keycenter hints.
- Does not execute SFZ scripts or claim full compliance with every vendor extension. Review parser output before using it as final sample mapping.

### Tests

The GitHub Actions workflow `.github/workflows/library-manager-tests.yml` compiles the Python modules and runs SFZ regression tests on Windows with Python 3.11.

### Safety

- Original files are never changed.
- Automatic filename hints are not treated as final musical classification.
- Archives are inventoried only; they are not extracted.
- Unsupported files are skipped, not deleted.
- Copy/sort mode remains a separate future stage requiring preview, collision checks, checksum verification, a transaction journal and rollback.

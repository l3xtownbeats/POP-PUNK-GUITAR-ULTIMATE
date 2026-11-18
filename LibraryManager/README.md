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


## Required preparation for MELODY MODE and PATTERN MODE

The Library Manager is responsible for preparing pitch-specific playable note material for the plugin; it must not merely catalogue a long source recording or assign one identical clip to every MIDI key.

The planned extraction/mapping stage must:

- identify individual note events inside WAV/SFZ-backed recordings, riffs, loops and longer phrases where boundaries are reliable;
- export each approved candidate as an independently addressable derived WAV clip in staging, preserving the source recording untouched;
- record exact source start/end sample positions, source and derived SHA-256, estimated MIDI pitch/note and confidence, articulation/performance character, velocity/dynamic layer where detectable, parent asset and review/license status;
- prepare distinct pitch-specific note-zone candidates for both MELODY MODE and PATTERN MODE;
- for PATTERN MODE, associate compatible pitch-specific notes with the same selected articulation/performance style (for example palm mute or downstroke), so changing MIDI pitch changes the note sound without changing the selected playing character;
- retain whole takes, parent loops and coherent phrases as parent/reference assets, with child note clips linked to their exact source offsets;
- report uncertain boundaries, uncertain note estimates and missing pitch/articulation zones for human review rather than inventing labels or silently reusing unrelated sounds.

The Manager's output is consumed by the plugin's per-key playback engine: MIDI key → pitch-specific approved note clip → independent voice playback. The plugin handles real-time note-on/note-off, polyphony and release; the Manager handles source analysis, extraction, metadata, review and mapping preparation.

**Safety:** this is a target capability, not part of the current 0.2.0 scanner. The current scanner remains read-only inventory/SFZ audit until the extraction stage is implemented and tested. Derived audio must stay in staging pending approval; never modify or move source files automatically.

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


## Extract meaningful guitar patterns; keep full recordings optional

The Manager must not simply add every full WAV as the default asset. It must inspect the recording and identify coherent guitar sections by musical role and changing rhythm/articulation.

- Extract each useful, internally coherent rhythmic guitar passage or pattern as a separate derived WAV clip.
- When the rhythm or articulation changes, create separate candidates at reliable musical boundaries rather than bundling unlike sections into one asset.
- Preserve complete phrases and their natural attack/decay; do not arbitrarily chop a pattern into tiny events.
- Also derive child note/chord events where boundaries and pitch estimates are reliable, retaining parent/child provenance.
- Retain the complete original recording as an optional whole-take asset/reference. It may be offered as a separate user-selectable item, but it is not the default substitute for extracted patterns.
- The user must be able to choose the exact extracted pattern/phrase, an individual note asset, or the complete recording where that is deliberately wanted.
- Store extracted candidates in staging for preview and approval. Do not copy them into FACTORY automatically.

This does not make a full pattern or whole WAV the payload for ordinary MELODY MODE/PATTERN MODE key presses: those modes continue to use their individual pitch-specific note mappings. Full rhythm excerpts and whole takes remain separately selectable library assets for preview or other explicitly supported uses.

## Approved instrument architecture reference

The approved product direction follows the broad player-facing workflow of Native Instruments SESSION GUITARIST — ELECTRIC SUNBURST DELUXE, implemented with original code and legally distributable source material. The architecture has two complementary engines:

- **PATTERN INSTRUMENT:** chord input drives a selected guitar rhythm/pattern performance; chord changes adapt the harmony while retaining the selected pattern identity wherever mappings support it.
- **MELODY INSTRUMENT:** ordinary MIDI keys play pitch-specific individual note clips. The already-approved note-playable PATTERN MODE remains distinct: one key triggers one note clip with the selected articulation/performance character.

Do not create a third standalone CHORD/PERFORMANCE instrument: chord-driven pattern performance belongs to PATTERN INSTRUMENT. Do not confuse that chord-driven engine with the existing one-key/one-note PATTERN MODE contract. Pattern Browser, documented MIDI Key Switches, articulation/performance controls, host-tempo sync where supported, and the project's own effects/tone section are planned player-facing capabilities.

The Manager must prepare both kinds of content: pitch-specific note assets/mappings for MELODY INSTRUMENT and note-playable PATTERN MODE; coherent rhythm/pattern/phrase assets plus reviewed chord/performance mapping candidates for PATTERN INSTRUMENT. It must preserve provenance, confidence and license/review state, and keep derived audio in staging until approval.

**This is an approved target architecture, not a statement that the chord-performance engine, chord recognition, Pattern Browser, Key Switches or extraction pipeline are implemented.** See docs/KEYBOARD_PLAYBACK_SPEC.md, section 14, for the full requirements and acceptance criteria.

## 15. Two distinct playable content sets — PATTERN INSTRUMENT and MELODY INSTRUMENT

The Manager must prepare and classify source material according to the actual playback job it can serve. It is not enough to put every guitar WAV into one generic folder or make one universal mapping.

### A. PATTERN INSTRUMENT — chord-driven guitar patterns

Prepare coherent, musically useful performances for the chord-driven Pattern Instrument:
- full rhythm patterns, riffs, strumming figures, arpeggios and multi-bar phrases;
- power-chord and open-chord performances, chord progressions and chord changes;
- palm-muted, open, partially muted and mixed muted/open parts;
- downstroke, upstroke, alternate picking, chugging, syncopation, gallop, stops, accents and other verified rhythmic feels;
- genre/style tags across pop-punk and related guitar styles, plus tone and articulation tags;
- phrase boundaries, tempo/meter estimates, chord-event timelines and confidence where analysis supports them.

Keep the coherent pattern/phrase as a selectable asset. Where reliable, also create linked child chord, note and articulation events. Preserve the parent phrase and exact source offsets. Pattern Instrument mappings must identify which patterns can adapt to which chord qualities/voicings. Do not claim a pattern is chord-adaptable merely because it has a chord label; flag unsupported or uncertain chord mappings for review.

### B. MELODY INSTRUMENT — individual guitar notes

Prepare a separate pitch-specific playable note collection:
- each MIDI key maps to one appropriate individual recorded guitar note/zone;
- include clean, crunch, overdrive, distortion, acoustic and other available tone families;
- include verified articulation variants such as palm-muted, open, downstroke, alternate-picked, slide, bend, harmonic and sustain where actual samples exist;
- retain velocity/dynamic layers, round robins, string/fret/source-note information when present or reliably detectable;
- generate key-zone maps and explicit missing-note/articulation reports.

The Melody Instrument must not receive a whole riff, chord progression or rhythm loop as the payload for an ordinary note key. A key press plays one mapped guitar note only. Do not fill the keyboard by repeating one unrelated sample across all keys; any bounded pitch-shift fallback must be explicit and quality-controlled.

### C. Cross-library organization

A source recording may contribute to both engines, but the derived assets and mappings must remain distinct and linked to the same source provenance. One audio asset may have multiple verified style/category tags without making duplicate physical copies. Keep the user's single approved Samples root and its three folders unchanged. All newly derived assets remain in LibraryManager/staging until review and license approval.

### Acceptance checks

1. Pattern Instrument browser exposes coherent rhythm/phrase assets and their verified chord/performance compatibility.
2. Melody Instrument mapping exposes pitch-specific individual guitar notes, not full patterns or chord progressions.
3. The same source may produce linked assets for both engines without losing parent/child provenance.
4. Missing pitch zones or unsupported chord adaptations are reported, never silently fabricated.
5. Pattern and Melody assets can be previewed independently and are routed to the correct engine.


## 16. Mandatory PATTERN MODE product workflow reference

The PATTERN MODE player workflow must be designed and implemented to follow the high-level interaction mechanics of Native Instruments SESSION GUITARIST – ELECTRIC SUNBURST DELUXE Pattern mode. This is a mandatory functional benchmark, not merely a visual reference. The selected pattern/playing feel remains consistent while the player's MIDI notes determine the changing pitches. Pattern selection, playable keys, key switches, dynamics, note lengths/release and articulation changes must work as one coherent playable instrument. Do not trigger a fixed prerecorded riff on every key. Prepare pitch-specific note assets and mappings for the playable range, report missing notes, and disclose any bounded pitch-shift fallback. Keep this separate from the chord-driven PATTERN INSTRUMENT workflow. Use only original implementation, original UI and properly licensed audio; do not copy proprietary code or protected assets. See `docs/KEYBOARD_PLAYBACK_SPEC.md`, section 17, for acceptance criteria.


## 17. First implemented extraction primitive — reviewed WAV ranges (0.1.0)

`asset_pipeline.py` now provides a real, tested foundation for creating derived audio clips without touching the source:
- extracts an explicitly reviewed sample-frame range from uncompressed PCM WAV;
- preserves source sample rate, channels and sample width;
- writes the derived clip only to `LibraryManager/staging/clips`;
- creates a JSON sidecar with source/derived SHA-256, exact sample/time offsets, parent ID, asset kind, engine targets, extractor version and review/license status;
- allows one derived clip to target more than one engine without making duplicate audio copies;
- rejects invalid ranges, unsupported engines and unsupported compressed WAV input.

This is intentionally a **reviewed-boundary extraction primitive**, not automatic musical segmentation. It does not yet detect notes, chords, bars, loops, tempo, articulation or phrase boundaries by listening to audio. Those require subsequent analysis modules and dedicated test fixtures. Source files remain unchanged, and staged clips are not promoted to FACTORY.

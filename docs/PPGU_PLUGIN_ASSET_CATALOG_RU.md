# POP PUNK GUITAR ULTIMATE — Plugin Asset Catalog Contract

Schema: `ppgu.plugin_asset_catalog/1.0.0`

This contract is produced by Library Manager 2.4.0. It is the handoff from non-destructive library analysis/staging to the future PPGU VST3 loader. It does not contain proprietary Session Guitarist code or content.

## Catalog location and paths

A full Manager cycle writes `plugin_asset_catalog.json` inside its run report folder. Each `asset_file` and `manifest_file` is a POSIX-style relative path resolved from the catalog file's directory. WAV payloads remain under `LibraryManager/staging/clips`; source recordings remain in their original locations and are never modified.

## Ten mode sections

The `modes` array always contains these entries, in order:

1. SAMPLE MODE — note zones, chord samples and Power Chords.
2. STRUMMING — confirmed Downstroke/Upstroke/chord-strumming performances.
3. ARPEGGIO — confirmed string-by-string voicing events.
4. PATTERN MODE — repeated rhythmic patterns and pitch-specific note zones.
5. RIFF MODE — reviewed riffs and characteristic fragments.
6. MELODY MODE — pitch-specific notes and melody sequences.
7. PHRASE MODE — complete reviewed phrases.
8. ONE PITCH — verified rhythmic material at one pitch.
9. ARTICULATIONS — reviewed Palm Mute/Open/Slide/Legato layers.
10. ENDING — reviewed musical endings.

Each mode includes `status`, `candidate_count`, `asset_count`, `playable_asset_count`, `candidates[]` and `assets[]`. A candidate is analysis evidence only; it has no playable WAV binding unless an extracted asset is separately present.

## Runtime asset fields

Each staged asset exposes:
- `asset_id`, `kind`, `target_modes`;
- `asset_file` and `manifest_file` relative to the catalog;
- `source_path`, `source_sha256`, `source_start_sample`, `source_end_sample`;
- `sample_rate`, `channels`, `frame_count`, `duration_seconds`;
- `derived_sha256`;
- note/chord candidate fields, articulation candidates and velocity candidate when available;
- `review_status`, `license_status`, `license_evidence`, `integrity_status`, `playable`, `blocking_reasons`.

A note-event asset can be referenced by SAMPLE MODE and note-playable PATTERN MODE. The catalog deduplicates it in the top-level `playable_assets` array by `asset_id`; mode references remain distinct.

## Mandatory runtime gates

An asset is `playable: true` only if all conditions hold:
1. The derived WAV exists inside staging and matches `derived_sha256`.
2. The original source exists and matches `source_sha256`.
3. Source offsets and frame count are valid.
4. `review_status == REVIEWED`.
5. `license_status == LICENSE_APPROVED`.
6. License evidence and all explicit `review_validation` flags are present.

Unreviewed assets may be browsed and previewed by Manager but must never enter the plugin's playable factory set. Never infer chord labels, MIDI notes, string/fret positions, tuning, velocity layers, articulation or license status from a missing field.

## Musical engine boundary

The catalog describes prepared sample payloads and analysis evidence. The VST3 runtime remains responsible for realtime MIDI note-on/off, voice/polyphony management, chord recognition, string/fret voicing generation, strumming/arpeggio scheduling, Pattern/Melody/Riff/Phrase/One Pitch execution, articulations, transitions, host transport/tempo sync and MIDI Key Switch.

- Chord adaptation must use reviewed pitch-specific note zones and reviewed voicings. Whole-loop WAV chromatic transposition is not an acceptable chord engine.
- Pattern selectors are control keys; they must not overlap the playable note/chord range. FL Studio 20 octave labels require host calibration.
- The audio callback must not perform file I/O, hashing, decoding or heavy analysis. Preload/stream assets through a bounded non-real-time layer.
- Preserve rhythm phase on chord change; articulate Palm Mute without stopping the pattern; apply Pattern changes on a musical boundary and release active voices safely.

## Known conservative queues

STRUMMING, ARPEGGIO, ARTICULATIONS and ENDING are not inferred from generic onset/RMS analysis. They remain explicit empty/manual-review sections until evidence is available. Long RMS-active regions remain in `unassigned_review_assets` and are not automatically called a riff, phrase or pattern.

## Status interpretation

- `CANDIDATES_ONLY_NO_APPROVED_RUNTIME_ASSETS`: catalog valid, but there are no assets that passed all musical/license/integrity gates.
- `READY_FOR_PLUGIN_IMPORT`: at least one asset passed every gate; this still does not mean the plugin has loaded or played it.

#!/usr/bin/env python3
"""Conservative WAV asset-kind classifier based on duration and envelope evidence.

Classification is a review candidate, never an automatic approval or file operation.
"""
from __future__ import annotations
import argparse
import json
import math
import statistics
import wave
from pathlib import Path

from audio_analysis import read_mono_pcm

def _median(values):
    return statistics.median(values) if values else 0.0

def _envelope(samples, rate, decimation, frame_ms=20, hop_ms=10):
    frame = max(1, round(rate * frame_ms / 1000 / decimation))
    hop = max(1, round(rate * hop_ms / 1000 / decimation))
    result = []
    for start in range(0, max(1, len(samples) - frame + 1), hop):
        chunk = samples[start:start + frame]
        if len(chunk) != frame:
            break
        result.append(math.sqrt(sum(x*x for x in chunk) / frame))
    return result, hop_ms / 1000.0

def _onsets(env, hop_seconds):
    if len(env) < 3:
        return []
    floor = max(0.006, max(env) * 0.10)
    rises = [max(0.0, env[i] - env[i-1]) for i in range(1, len(env))]
    positive = [x for x in rises if x > 0]
    threshold = max(0.008, _median(positive) * 2.5, max(rises, default=0) * 0.18)
    candidates = []
    last = -10**9
    for i, rise in enumerate(rises, 1):
        if rise >= threshold and env[i] >= floor and (i-last)*hop_seconds >= 0.075:
            candidates.append(i * hop_seconds)
            last = i
    return candidates

def _regularity(onsets):
    intervals = [b-a for a,b in zip(onsets, onsets[1:])]
    if len(intervals) < 3:
        return 0.0
    mean = statistics.fmean(intervals)
    if mean <= 0:
        return 0.0
    cv = statistics.pstdev(intervals) / mean
    return max(0.0, min(1.0, 1.0-cv))

def classify_wav(path: Path, short_max_seconds: float = 1.25,
                 long_min_seconds: float = 1.5) -> dict:
    path = Path(path)
    samples, rate, frames, channels, width, decimation = read_mono_pcm(path)
    if rate <= 0 or frames <= 0 or not samples:
        raise ValueError("Empty or invalid WAV")
    duration = frames / rate
    env, hop_seconds = _envelope(samples, rate, decimation)
    peak = max((abs(x) for x in samples), default=0.0)
    active = [x for x in env if x > max(0.003, peak*0.025)]
    if peak < 0.003 or not active:
        kind, subtype, confidence = "UNKNOWN", "UNKNOWN", 0.99
        evidence = ["No meaningful signal energy detected."]
        onset_times = []
        regularity = 0.0
    else:
        onset_times = _onsets(env, hop_seconds)
        regularity = _regularity(onset_times)
        first = next((i for i,x in enumerate(env) if x > max(0.003, peak*0.025)), 0)
        tail = env[max(first, len(env)-max(1, round(0.15/hop_seconds))):]
        tail_ratio = (_median(tail) / max(peak, 1e-9)) if tail else 0.0
        dynamic_range = (max(env)-min(env)) / max(peak, 1e-9)
        evidence = [f"Duration {duration:.3f}s.", f"{len(onset_times)} envelope attack candidates.",
                    f"Inter-onset regularity {regularity:.2f}.",
                    f"Tail RMS/peak ratio {tail_ratio:.2f}.",
                    f"Normalized envelope variation {dynamic_range:.2f}."]
        if duration <= short_max_seconds and len(onset_times) <= 2 and tail_ratio < 0.30:
            kind, subtype = "ONE_SHOT", "NOTE_ONE_SHOT"
            confidence = 0.78 if duration <= 0.65 else 0.68
            evidence.append("Short duration, few attacks and a decaying tail support a one-shot candidate.")
        elif duration >= long_min_seconds:
            kind = "SAMPLE"
            if len(onset_times) >= 4 and regularity >= 0.55:
                subtype, confidence = "RHYTHMIC", min(0.92, 0.68 + regularity*0.2)
                evidence.append("Long recording with repeated, reasonably regular envelope attacks.")
            elif len(onset_times) >= 3:
                subtype, confidence = "MULTI_HIT", 0.68
                evidence.append("Long recording contains multiple separated attack candidates.")
            elif tail_ratio >= 0.35:
                subtype, confidence = "SUSTAIN", 0.70
                evidence.append("Long, sustained energy without a clear repeated attack pattern.")
            else:
                subtype, confidence = "UNKNOWN", 0.52
                evidence.append("Long recording; subtype is not supported by envelope evidence.")
        else:
            kind, subtype, confidence = "UNKNOWN", "UNKNOWN", 0.48
            evidence.append("Duration and envelope evidence do not clearly separate a one-shot from a sample.")
    loop_candidate = bool(kind == "SAMPLE" and subtype == "RHYTHMIC" and regularity >= 0.75 and len(onset_times) >= 5)
    return {
        "classifier_version": "0.1.0",
        "source": str(path.resolve()),
        "duration_seconds": round(duration, 6),
        "asset_kind_candidate": kind,
        "sample_subtype_candidate": subtype,
        "loop_candidate": loop_candidate,
        "loop_status": "CANDIDATE_ONLY" if loop_candidate else "NOT_ESTABLISHED",
        "classification_confidence": round(confidence, 3),
        "evidence": evidence,
        "features": {"onset_count": len(onset_times),
                     "onset_times_seconds": [round(x, 4) for x in onset_times],
                     "inter_onset_regularity": round(regularity, 3),
                     "peak": round(peak, 6)},
        "review_status": "NEEDS_MUSICAL_REVIEW",
        "license_status": "UNREVIEWED",
        "source_modified": False,
        "limitations": [
            "Duration and amplitude envelope are heuristic evidence, not proof of musical role.",
            "Envelope attacks can be caused by dynamics, noise, compression or editing.",
            "Melodic and chordal subtypes require reliable pitch/chord event analysis and are not inferred here.",
            "A loop candidate is not a confirmed seamless loop; boundary and periodicity review is required.",
            "No source file is moved, renamed, deleted, extracted or modified."
        ]
    }

def main():
    parser = argparse.ArgumentParser(description="Classify WAV asset kind from conservative acoustic evidence.")
    parser.add_argument("wav", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--short-max", type=float, default=1.25)
    parser.add_argument("--long-min", type=float, default=1.5)
    args = parser.parse_args()
    result = classify_wav(args.wav, args.short_max, args.long_min)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

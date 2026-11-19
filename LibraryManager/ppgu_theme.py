"""PPGU NEON STAGE DEFAULT theme loader for Library Manager.

Logical PPGU gallery slot: SKIN-1.
Canonical source manifest: skin-053 / SKIN/Skin_053/theme.json.
The palette values are read from the bundled, unmodified PPGU manifest.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

LOGICAL_SKIN_SLOT = "SKIN-1"
CANONICAL_SKIN_ID = "skin-053"
CANONICAL_SKIN_NAME = "NEON STAGE DEFAULT"

PALETTE_KEYS = (
    "window_bg", "panel", "panel_elevated", "control_bg", "control_face",
    "control_border", "text_primary", "text_secondary", "text_disabled",
    "accent", "accent_glow", "danger", "warning", "success", "lcd_bg",
    "lcd_text", "led_on", "led_off", "shadow", "highlight", "lowlight",
)

# Exact 21-token fallback from PPGU SKIN/Skin_053/theme.json.
_FALLBACK_PALETTE = {
    "window_bg": "#0B0F12",
    "panel": "#141B20",
    "panel_elevated": "#1D2930",
    "control_bg": "#0F1519",
    "control_face": "#192329",
    "control_border": "#53656B",
    "text_primary": "#F3F7F5",
    "text_secondary": "#B7C5C2",
    "text_disabled": "#879791",
    "accent": "#D5FF45",
    "accent_glow": "#DEFF6E",
    "danger": "#FF5A66",
    "warning": "#FFC857",
    "success": "#6EE7A8",
    "lcd_bg": "#08110E",
    "lcd_text": "#D7FFB2",
    "led_on": "#D5FF45",
    "led_off": "#33443B",
    "shadow": "#050708",
    "highlight": "#90A7A0",
    "lowlight": "#0D1417",
}


def resource_path(*parts: str) -> Path:
    """Resolve bundled assets in source runs and PyInstaller onedir builds."""
    module_dir = Path(__file__).resolve().parent
    candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root))
    candidates.append(module_dir)

    for base in candidates:
        candidate = base.joinpath("ppgu_skin", *parts)
        if candidate.exists():
            return candidate
    return module_dir.joinpath("ppgu_skin", *parts)


def _valid_palette(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != set(PALETTE_KEYS):
        return False
    return all(
        isinstance(value.get(key), str)
        and re.fullmatch(r"#[0-9A-Fa-f]{6}", value[key]) is not None
        for key in PALETTE_KEYS
    )


def load_neon_stage_theme() -> dict[str, Any]:
    """Load the canonical manifest; use its exact token fallback if unavailable."""
    manifest_path = resource_path("theme.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        palette = manifest.get("palette")
        if (
            manifest.get("id") == CANONICAL_SKIN_ID
            and manifest.get("name") == CANONICAL_SKIN_NAME
            and _valid_palette(palette)
        ):
            return manifest
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        pass

    # UI remains launchable on a damaged/missing skin package, but its source
    # identity is made explicit so the packaging test can catch the omission.
    return {
        "schemaVersion": "1.0.0",
        "id": CANONICAL_SKIN_ID,
        "name": CANONICAL_SKIN_NAME,
        "palette": dict(_FALLBACK_PALETTE),
        "reduceInEco": True,
        "compatibility": {
            "apvtsChanges": False,
            "layoutChanges": False,
            "audioChanges": False,
        },
        "_fallback": True,
    }


NEON_STAGE_THEME = load_neon_stage_theme()
NEON_STAGE_PALETTE = NEON_STAGE_THEME["palette"]

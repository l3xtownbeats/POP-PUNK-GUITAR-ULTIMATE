"""PPGU NEON STAGE DEFAULT theme loader for Library Manager.

Logical PPGU gallery slot: SKIN-1.
Canonical source manifest: skin-053 / SKIN/Skin_053/theme.json.
The color tokens follow the user's approved NEON STAGE reference mockups; the skin identity and supporting art remain canonical.
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
    "accent", "accent_glow", "accent_purple", "accent_magenta",
    "danger", "warning", "success", "lcd_bg",
    "lcd_text", "led_on", "led_off", "shadow", "highlight", "lowlight",
)

# Approved 23-token NEON STAGE fallback, aligned to the reference mockups.
_FALLBACK_PALETTE = {
    "window_bg": "#000612",
    "panel": "#010B1C",
    "panel_elevated": "#06152E",
    "control_bg": "#000A1E",
    "control_face": "#06112A",
    "control_border": "#0B4E9C",
    "text_primary": "#F3F7FF",
    "text_secondary": "#B9CBE0",
    "text_disabled": "#788BA4",
    "accent": "#075CE8",
    "accent_glow": "#00BFFF",
    "accent_purple": "#7115B8",
    "accent_magenta": "#E51BD4",
    "danger": "#FF5577",
    "warning": "#FFC857",
    "success": "#57E879",
    "lcd_bg": "#02091E",
    "lcd_text": "#8CEAFF",
    "led_on": "#00C8FF",
    "led_off": "#18345A",
    "shadow": "#00020A",
    "highlight": "#3E9CFF",
    "lowlight": "#000612"
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

from __future__ import annotations

import re
import unittest

from ppgu_theme import (
    CANONICAL_SKIN_ID,
    CANONICAL_SKIN_NAME,
    LOGICAL_SKIN_SLOT,
    NEON_STAGE_PALETTE,
    NEON_STAGE_THEME,
    PALETTE_KEYS,
    resource_path,
)


class NeonStageThemeTests(unittest.TestCase):
    def test_logical_slot_resolves_to_canonical_skin_053(self) -> None:
        self.assertEqual(LOGICAL_SKIN_SLOT, "SKIN-1")
        self.assertEqual(CANONICAL_SKIN_ID, "skin-053")
        self.assertEqual(CANONICAL_SKIN_NAME, "NEON STAGE DEFAULT")
        self.assertEqual(NEON_STAGE_THEME["id"], CANONICAL_SKIN_ID)
        self.assertEqual(NEON_STAGE_THEME["name"], CANONICAL_SKIN_NAME)
        self.assertFalse(NEON_STAGE_THEME.get("_fallback", False))

    def test_all_23_palette_tokens_are_present_and_valid(self) -> None:
        self.assertEqual(set(NEON_STAGE_PALETTE), set(PALETTE_KEYS))
        for token, value in NEON_STAGE_PALETTE.items():
            with self.subTest(token=token):
                self.assertRegex(value, re.compile(r"^#[0-9A-Fa-f]{6}$"))

    def test_exact_ppgu_neon_stage_signature(self) -> None:
        self.assertEqual(NEON_STAGE_PALETTE["window_bg"], "#0B0F12")
        self.assertEqual(NEON_STAGE_PALETTE["panel"], "#141B20")
        self.assertEqual(NEON_STAGE_PALETTE["accent"], "#078BFF")
        self.assertEqual(NEON_STAGE_PALETTE["accent_glow"], "#16D4FF")
        self.assertEqual(NEON_STAGE_PALETTE["accent_purple"], "#8B5CFF")
        self.assertEqual(NEON_STAGE_PALETTE["accent_magenta"], "#F02DCE")
        self.assertEqual(NEON_STAGE_PALETTE["lcd_bg"], "#030A17")
        self.assertEqual(NEON_STAGE_PALETTE["lcd_text"], "#8CEAFF")
        self.assertTrue(NEON_STAGE_THEME["reduceInEco"])

    def test_theme_is_visual_only(self) -> None:
        compatibility = NEON_STAGE_THEME["compatibility"]
        self.assertFalse(compatibility["apvtsChanges"])
        self.assertFalse(compatibility["layoutChanges"])
        self.assertFalse(compatibility["audioChanges"])

    def test_real_neon_stage_art_assets_are_bundled(self) -> None:
        required = (
            resource_path("theme.json"),
            resource_path("assets", "hero.png"),
            resource_path("assets", "preview.png"),
            resource_path("svg", "bezel.svg"),
            resource_path("svg", "crest.svg"),
            resource_path("svg", "texture.svg"),
            resource_path("icons", "import_guitar.svg"),
            resource_path("icons", "settings.svg"),
            resource_path("icons", "skins.svg"),
        )
        for path in required:
            with self.subTest(path=str(path)):
                self.assertTrue(path.is_file(), f"Missing PPGU theme asset: {path}")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

import gallery


class GalleryPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.themes = gallery.load_themes()

    def test_current_fixture_contains_36_unique_presets(self) -> None:
        names = [str(theme["name"]) for theme in self.themes]
        self.assertEqual(36, len(names))
        self.assertEqual(len(names), len(set(names)))

    def test_every_mode_has_required_tokens_and_dark_inherits_light(self) -> None:
        for theme in self.themes:
            with self.subTest(theme=theme["name"]):
                payload = gallery.theme_payload(theme)
                light = payload["modes"]["light"]
                dark = payload["modes"]["dark"]
                self.assertTrue(gallery.REQUIRED_TOKENS <= light.keys())
                self.assertTrue(gallery.REQUIRED_TOKENS <= dark.keys())
                source_light = theme["cssVars"].get("light", {})
                for name, value in source_light.items():
                    self.assertEqual(
                        theme["cssVars"].get("dark", {}).get(name, value),
                        dark[name],
                    )
                for mode in ("light", "dark"):
                    self.assertEqual(
                        set(payload["diagnostics"][mode]),
                        {"background", "muted", "border", "foreground", "primary", "destructive"},
                    )

    def test_rejects_unsafe_token_names_and_values(self) -> None:
        invalid_name = copy.deepcopy(self.themes[0])
        invalid_name["cssVars"]["light"]["bad;name"] = "red"
        with self.assertRaisesRegex(ValueError, "invalid CSS token name"):
            gallery.theme_payload(invalid_name)

        invalid_value = copy.deepcopy(self.themes[0])
        invalid_value["cssVars"]["light"]["primary"] = "url(https://example.test/x)"
        with self.assertRaisesRegex(ValueError, "unsafe CSS token value"):
            gallery.theme_payload(invalid_value)

    def test_empty_registry_has_descriptive_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text('{"items": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contains no theme presets"):
                gallery.load_themes(path)


class GalleryArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.themes = gallery.load_themes()
        cls.generated = gallery.build_html(cls.themes)

    def test_checked_in_artifact_matches_deterministic_build(self) -> None:
        self.assertEqual(
            self.generated,
            gallery.OUTPUT_PATH.read_text(encoding="utf-8"),
        )
        self.assertEqual([], gallery.verify_gallery())

    def test_artifact_has_static_offline_guards_and_semantic_sections(self) -> None:
        self.assertIn("Content-Security-Policy", self.generated)
        self.assertIn("connect-src 'none'", self.generated)
        self.assertIn("style.setProperty", self.generated)
        self.assertNotIn("style.cssText", self.generated)
        self.assertNotRegex(self.generated, r"https?://|//[A-Za-z0-9.-]+/")
        for section in gallery.SECTIONS:
            self.assertIn(f'id="{section.lower()}"', self.generated)

    def test_full_retheme_specimen_markers_are_present(self) -> None:
        for marker in (
            'aria-label="Segmented view"',
            'id="password" type="password"',
            "Popover &amp; sheet",
            "role=\"separator\"",
            "<details>",
            "sidebar-primary",
            "sidebar-ring",
            "aria-label=\"Asset generation progress\"",
            'id="shell"',
            'aria-label="Niri-aware top bar specimen"',
            "Control Center",
            'aria-label="Launcher results"',
            "On-screen display",
            'class="notification-stack"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.generated)

    def test_graphite_is_the_default_reference_preset(self) -> None:
        self.assertIn('<option value="graphite" selected>Graphite</option>', self.generated)
        self.assertNotIn("data-preset", self.generated)

    def test_shell_icons_are_local_inline_svg(self) -> None:
        shell = re.search(
            r'<section class="spec-section shell-overview" id="shell".*?'
            r'<section class="spec-section" id="actions"',
            self.generated,
            re.S,
        )
        if shell is None:
            self.fail("generated shell section is missing")
        shell_markup = shell.group(0)
        self.assertGreaterEqual(shell_markup.count('class="icon-svg"'), 10)
        for glyph in "⌕ᛒ☾♢◇Ⅱ✓↓♩◒☀⌁◉＋":
            self.assertNotIn(glyph, shell_markup)
        self.assertNotIn("<script src=", self.generated)
        self.assertNotIn("lineIcon", self.generated)
        self.assertNotIn("insertAdjacentHTML", self.generated)

    def test_complete_shell_surface_contract_is_present(self) -> None:
        for marker in (
            'aria-label="Dock state specimen"',
            "Auto-hide edge",
            'aria-label="Lock and session state specimen"',
            'id="shell-password" type="password"',
            'aria-label="Settings window specimen"',
            "Widget editor",
            'aria-label="Local wallpaper choices"',
            'aria-label="Clipboard preview"',
            'aria-label="Screenshot utility preview"',
            'aria-label="Desktop widget canvas and edit state specimen"',
            'aria-label="Selected widget edit frame"',
            'aria-label="Niri compositor integration fixture:',
            "Theme Forge previews their integration boundary",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.generated)

    def test_shell_compositions_are_honestly_inert(self) -> None:
        self.assertGreaterEqual(self.generated.count('data-preview="inert"'), 7)
        shell = re.search(
            r'<section class="spec-section shell-overview" id="shell".*?'
            r'<section class="spec-section" id="actions"',
            self.generated,
            re.S,
        )
        if shell is None:
            self.fail("generated shell section is missing")
        shell_markup = shell.group(0)
        self.assertNotIn("onclick=", shell_markup)
        self.assertIn("Niri owns overview, workspace animation, tiling, focus", shell_markup)
        controls = re.findall(
            r"<(?:button|input|select|textarea)\b[^>]*>", shell_markup
        )
        self.assertGreater(len(controls), 10)
        for control in controls:
            with self.subTest(control=control):
                self.assertRegex(control, r"\sdisabled(?:\s|>)")

    def test_visual_shell_fixtures_expose_accessible_roles(self) -> None:
        for marker in (
            'class="dock-stage" role="group" aria-label="Dock state specimen"',
            'class="widget-canvas" role="group"',
            'class="sysmon-bars" role="img"',
            'class="edit-frame" role="group"',
            'class="niri-window-map" role="img"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.generated)

    def test_initial_hash_navigation_preserves_direct_shell_links(self) -> None:
        self.assertIn("function syncInitialScroll()", self.generated)
        self.assertIn("window.location.hash", self.generated)
        self.assertIn("target.scrollIntoView()", self.generated)
        self.assertIn("else window.scrollTo(0, 0)", self.generated)
        self.assertNotIn("applyTheme();\nwindow.scrollTo(0, 0)", self.generated)

    def test_displayed_preset_count_is_registry_driven(self) -> None:
        generated = gallery.build_html([self.themes[0]])
        self.assertIn("1 presets · Offline", generated)
        self.assertIn("Theme presets <span>1</span>", generated)
        self.assertNotIn("36 presets", generated)

    def test_dashboard_token_values_are_bound_to_active_theme_data(self) -> None:
        self.assertIn("data-token-name='background'", self.generated)
        self.assertIn("theme.diagnostics[mode][item.dataset.tokenName]", self.generated)

    def test_verifier_rejects_preset_specific_specimen_css(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "index.html"
            output.write_text(
                self.generated.replace(
                    "/* SPECIMEN_CSS_END */",
                    ".specimen[data-preset=graphite]{color:var(--foreground)}"
                    "/* SPECIMEN_CSS_END */",
                ),
                encoding="utf-8",
            )
            errors = gallery.verify_gallery(output=output)
            self.assertIn("specimen CSS contains a preset-specific branch", errors)

    def test_verifier_detects_registry_content_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = root / "registry.json"
            output = root / "index.html"
            changed = {"items": copy.deepcopy(self.themes)}
            changed["items"][0]["title"] = "Changed title"
            registry.write_text(json.dumps(changed), encoding="utf-8")
            output.write_text(self.generated, encoding="utf-8")
            errors = gallery.verify_gallery(output=output, registry_path=registry)
            self.assertIn(
                "generated artifact differs from deterministic registry build",
                errors,
            )


if __name__ == "__main__":
    unittest.main()

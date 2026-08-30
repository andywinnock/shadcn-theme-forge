import contextlib
import io
import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import forge


def sample_item(name="sample", *, theme=None, light=None, dark=None):
    css_vars = {}
    if theme is not None:
        css_vars["theme"] = theme
    if light is not None:
        css_vars["light"] = light
    if dark is not None:
        css_vars["dark"] = dark
    return {
        "name": name,
        "title": name.title(),
        "description": "A test theme",
        "cssVars": css_vars,
    }


BASE_TOKENS = {
    "background": "#ffffff",
    "foreground": "#111111",
    "primary": "#336699",
    "primary-foreground": "#ffffff",
    "accent": "#eeeeee",
    "muted": "#dddddd",
    "muted-foreground": "#555555",
    "destructive": "#cc0000",
    "border": "#cccccc",
    "ring": "#336699",
}


class MapModeTests(unittest.TestCase):
    def test_maps_semantic_tokens_to_noctalia_roles(self):
        palette = forge.map_mode(
            {
                **BASE_TOKENS,
                "ring": "#123456",
                "ring-foreground": "#abcdef",
                "chart-2": "#654321",
                "shadow-color": "#010203",
            }
        )

        self.assertEqual(
            {
                "primary": palette["primary"],
                "secondary": palette["secondary"],
                "onSecondary": palette["onSecondary"],
                "tertiary": palette["tertiary"],
                "shadow": palette["shadow"],
                "hover": palette["hover"],
            },
            {
                "primary": "#336699",
                "secondary": "#123456",
                "onSecondary": "#abcdef",
                "tertiary": "#654321",
                "shadow": "#010203",
                "hover": "#eeeeee",
            },
        )

    def test_warns_and_falls_back_when_shadow_color_is_unsupported(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            palette = forge.map_mode(
                {**BASE_TOKENS, "background": "#fefefe", "shadow-color": "hsl(0 0% 0% / 0.1)"}
            )

        self.assertEqual(palette["shadow"], "#fefefe")
        self.assertTrue(any("shadow-color" in str(w.message) for w in caught))


class PaletteModeTests(unittest.TestCase):
    def test_copies_dark_palette_when_light_mode_is_missing(self):
        palette = forge.noctalia_palette(sample_item(dark=BASE_TOKENS))

        self.assertEqual(palette["light"], palette["dark"])

    def test_copies_light_palette_when_dark_mode_is_missing(self):
        palette = forge.noctalia_palette(sample_item(light=BASE_TOKENS))

        self.assertEqual(palette["dark"], palette["light"])

    def test_rejects_theme_when_both_color_modes_are_missing(self):
        with self.assertRaisesRegex(ValueError, "sample: no cssVars modes"):
            forge.noctalia_palette(sample_item())


class WebTokenTests(unittest.TestCase):
    def test_canonical_modes_follow_root_and_dark_cascade(self):
        modes = forge.web_mode_tokens(
            sample_item(
                theme={"font-sans": "Shared Sans", "tracking-tight": "-0.025em"},
                light={"background": "white", "primary": "blue"},
                dark={"background": "black", "primary": "cyan"},
            )
        )

        self.assertEqual(
            modes["light"],
            {
                "font-sans": "Shared Sans",
                "tracking-tight": "-0.025em",
                "background": "white",
                "primary": "blue",
            },
        )
        self.assertEqual(
            modes["dark"],
            {
                "font-sans": "Shared Sans",
                "tracking-tight": "-0.025em",
                "background": "black",
                "primary": "cyan",
            },
        )

    def test_dark_mode_inherits_light_tokens_not_explicitly_overridden(self):
        modes = forge.web_mode_tokens(
            sample_item(
                theme={"radius": "0.5rem"},
                light={"shadow-x": "1px", "background": "white"},
                dark={"background": "black"},
            )
        )

        self.assertEqual(modes["dark"]["shadow-x"], "1px")

    def test_css_emits_shared_and_light_tokens_in_root_with_dark_overrides(self):
        css = forge.css_text(
            sample_item(
                theme={"tracking-tight": "calc(var(--tracking-normal) - 0.025em)"},
                light={"tracking-normal": "0em", "background": "white"},
                dark={"background": "black"},
            )
        )

        root, dark = css.split("  .dark, [data-theme=dark] {")
        self.assertIn("--tracking-tight: calc(var(--tracking-normal) - 0.025em);", root)
        self.assertIn("--tracking-normal: 0em;", root)
        self.assertIn("--background: white;", root)
        self.assertIn("--background: black;", dark)
        self.assertNotIn("--tracking-tight", dark)


class MainTests(unittest.TestCase):
    def test_read_only_registry_fetch_does_not_create_cache(self):
        registry = {"items": []}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(registry).encode()

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "registry.json"
            with (
                mock.patch.object(forge, "CACHE", cache),
                mock.patch.object(forge.urllib.request, "urlopen", return_value=Response()),
            ):
                loaded = forge.load_registry(write_cache=False)

            self.assertEqual(loaded, registry)
            self.assertFalse(cache.exists())

    def test_dry_run_does_not_write_and_reports_selected_theme_count(self):
        registry = {
            "items": [
                sample_item("first", light=BASE_TOKENS, dark=BASE_TOKENS),
                sample_item("second", light=BASE_TOKENS, dark=BASE_TOKENS),
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out_dir = root / "out"
            out_dir.mkdir()
            manifest = out_dir / "index.json"
            manifest.write_text('{"sentinel": true}')
            palette_dir = root / "palettes"
            stdout = io.StringIO()

            with (
                mock.patch.object(forge, "OUT_DIR", out_dir),
                mock.patch.object(forge, "load_registry", return_value=registry),
                mock.patch.object(
                    sys,
                    "argv",
                    ["forge.py", "--dry-run", "--only", "first", "--noctalia-dir", str(palette_dir)],
                ),
                contextlib.redirect_stdout(stdout),
            ):
                result = forge.main()

            self.assertEqual(result, 0)
            self.assertEqual(manifest.read_text(), '{"sentinel": true}')
            self.assertFalse((out_dir / "css").exists())
            self.assertFalse(palette_dir.exists())
            self.assertIn("1 theme selected", stdout.getvalue())


class GeneratedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.registry = json.loads((root / "registry.json").read_text())
        cls.manifest = json.loads((root / "out" / "index.json").read_text())
        cls.root = root

    def test_manifest_has_one_well_shaped_entry_per_registry_theme(self):
        expected = {item["name"] for item in self.registry["items"]}
        themes = self.manifest["themes"]

        self.assertEqual({theme["name"] for theme in themes}, expected)
        self.assertTrue(all({"name", "title", "description"} <= theme.keys() for theme in themes))

    def test_each_manifest_theme_has_css_and_palette_artifacts(self):
        missing = []
        for theme in self.manifest["themes"]:
            name = theme["name"]
            if not (self.root / "out" / "css" / "tweakcn" / f"{name}.css").is_file():
                missing.append(f"css:{name}")
            if not (self.root / "out" / "palettes-test" / f"{name}.json").is_file():
                missing.append(f"palette:{name}")

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()

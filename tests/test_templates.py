import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import templates


class AdapterDescriptorTests(unittest.TestCase):
    def test_canonical_adapter_descriptor_is_complete_and_unique(self):
        expected = (
            ("shadcn_gtk3", "gtk3.css", "$XDG_CONFIG_HOME/gtk-3.0/noctalia.css"),
            ("shadcn_gtk4", "gtk4.css", "$XDG_CONFIG_HOME/gtk-4.0/noctalia.css"),
            ("shadcn_kitty", "kitty.conf", "$XDG_CONFIG_HOME/kitty/themes/shadcn.conf"),
            ("shadcn_foot", "foot.ini", "$XDG_CONFIG_HOME/foot/noctalia.ini"),
            ("shadcn_alacritty", "alacritty.toml", "$XDG_CONFIG_HOME/alacritty/noctalia.toml"),
            ("shadcn_wezterm", "wezterm.lua", "$XDG_CONFIG_HOME/wezterm/noctalia.lua"),
            ("shadcn_waybar", "waybar.css", "$XDG_CONFIG_HOME/waybar/noctalia.css"),
        )
        self.assertEqual(
            tuple((adapter.name, adapter.filename, adapter.output_path) for adapter in templates.ADAPTERS),
            expected,
        )
        self.assertEqual(len({adapter.name for adapter in templates.ADAPTERS}), 7)
        self.assertEqual(len({adapter.filename for adapter in templates.ADAPTERS}), 7)
        manifest = templates.templates_manifest()
        for adapter in templates.ADAPTERS:
            self.assertIn(f"[templates.{adapter.name}]", manifest)
            self.assertIn(adapter.filename, manifest)
            self.assertIn(adapter.output_path, manifest)

    def test_verify_rejects_invalid_mode_and_missing_template(self):
        with self.assertRaisesRegex(ValueError, "invalid render mode"):
            templates.verify("graphite", mode="sepia")
        with self.assertRaisesRegex(ValueError, "template does not exist"):
            templates.verify("graphite", Path("missing.template"))

    def test_verify_fails_closed_on_nonzero_engine_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            preview_dir = root / "preview"
            preview_dir.mkdir()
            (preview_dir / "graphite.json").write_text(json.dumps({"light": {"primary": "#ffffff"}}))
            template = root / "sample.css"
            template.write_text("color: {{ colors.primary.default.hex }}")
            with mock.patch.object(templates, "PREVIEW_DIR", preview_dir), mock.patch(
                "templates.subprocess.run",
                return_value=subprocess.CompletedProcess([], 9, "", "engine failed"),
            ):
                self.assertFalse(templates.verify("graphite", template, mode="light"))

    def test_native_matrix_is_exactly_seven_adapters_by_two_modes(self):
        payload = {
            "light": {"primary": "#111111", "terminal_background": "#222222"},
            "dark": {"primary": "#eeeeee", "terminal_background": "#dddddd"},
        }
        with mock.patch.object(Path, "read_text", return_value=json.dumps(payload)), mock.patch.object(
            templates, "verify", return_value=True
        ) as verify:
            self.assertTrue(templates.verify_native_matrix())

        self.assertEqual(verify.call_count, 14)
        self.assertEqual(
            {(call.args[0], call.kwargs["mode"]) for call in verify.call_args_list},
            {("graphite", "light"), ("cosmic-night", "dark")},
        )
        self.assertTrue(all(call.kwargs["sentinel"] for call in verify.call_args_list))
        self.assertTrue(all(call.kwargs["expected_color"] for call in verify.call_args_list))

    def test_native_matrix_fails_when_any_render_fails(self):
        payload = {
            "light": {"primary": "#111111", "terminal_background": "#222222"},
            "dark": {"primary": "#eeeeee", "terminal_background": "#dddddd"},
        }
        outcomes = [True] * 13 + [False]
        with mock.patch.object(Path, "read_text", return_value=json.dumps(payload)), mock.patch.object(
            templates, "verify", side_effect=outcomes
        ) as verify:
            self.assertFalse(templates.verify_native_matrix())

        self.assertEqual(verify.call_count, 14)

    def test_gtk_templates_include_component_geometry(self):
        for template in (templates.GTK3_TEMPLATE, templates.GTK4_TEMPLATE):
            self.assertIn("border-radius: 8px", template)
            self.assertIn("button.suggested-action", template)
            self.assertIn("button.destructive-action", template)
            self.assertIn("row:selected", template)
            self.assertIn("box-shadow: 0 0 0 2px", template)
            self.assertIn("popover.menu > contents", template)
            self.assertIn("background-color: transparent", template)
        self.assertNotIn(":root", templates.GTK3_TEMPLATE)
        self.assertIn("--window-bg-color", templates.GTK4_TEMPLATE)


if __name__ == "__main__":
    unittest.main()

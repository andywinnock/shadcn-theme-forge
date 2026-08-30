import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "native/noctalia/patches/0001-shadcn-component-profile.patch"
BUILD = ROOT / "native/noctalia/build_native.sh"
LOCK_VERIFY = ROOT / "native/noctalia/verify_lock_nested.sh"


class NativeNoctaliaProfileTests(unittest.TestCase):
    def test_patch_owns_component_geometry_not_colors(self) -> None:
        text = PATCH.read_text()
        for symbol in (
            "radiusSm",
            "radiusMd",
            "radiusLg",
            "radiusXl",
            "cardPadding",
            "panelPadding",
            "controlHeight",
            "animNormal",
        ):
            self.assertIn(symbol, text)
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{6}\b", text))

    def test_patch_covers_named_shell_surfaces(self) -> None:
        text = PATCH.read_text()
        for path in (
            "dock_geometry.cpp",
            "calendar_view.cpp",
            "notification_toast.cpp",
            "osd_overlay.cpp",
            "dock_items.cpp",
            "session_panel.cpp",
            "lockscreen_login_box.h",
        ):
            self.assertIn(path, text)
        for symbol in ("controlRadius", "cardRadius", "floatingSurfaceRadius", "buttonHeight"):
            self.assertIn(symbol, text)
        self.assertIn("kCellPad = static_cast<std::int32_t>(Style::spaceSm)", text)

    def test_build_is_pinned_and_user_local(self) -> None:
        text = BUILD.read_text()
        self.assertRegex(text, r'upstream_commit="[0-9a-f]{40}"')
        self.assertIn("out/native/noctalia-root", text)
        self.assertNotIn("sudo", text)
        self.assertNotIn("/usr/bin/noctalia", text)
        self.assertIn("git -C \"${source_dir}\" apply --check", text)
        self.assertNotIn("reset --hard", text)
        self.assertIn("profile_tests", text)
        self.assertIn("-Dtests=enabled", text)
        self.assertIn('meson compile -C "${build_dir}"', text)
        self.assertIn('meson install --no-rebuild -C "${build_dir}"', text)
        self.assertNotIn("just --justfile", text)
        self.assertIn('"${#listed_tests[@]}" -lt 90', text)
        self.assertIn("upower_charge_limit_integration", text)
        self.assertTrue((ROOT / "native/noctalia/KNOWN_LIMITATIONS.md").is_file())

    def test_lock_verifier_is_nested_and_never_targets_the_parent_session(self) -> None:
        text = LOCK_VERIFY.read_text()
        self.assertIn("mktemp -d /tmp/shadcn-nested-lock", text)
        self.assertIn("niri -c", text)
        self.assertIn('msg session lock', text)
        self.assertIn('msg theme-mode-set "${SHADCN_THEME_MODE}"', text)
        self.assertIn('XDG_RUNTIME_DIR="${SHADCN_PARENT_RUNTIME}"', text)
        self.assertNotIn("loginctl", text)
        self.assertNotIn("systemctl", text)
        self.assertNotIn("sudo", text)
        syntax = subprocess.run(
            ["bash", "-n", str(LOCK_VERIFY)], text=True, capture_output=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)


if __name__ == "__main__":
    unittest.main()

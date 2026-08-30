import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "native/qt/manage.py"
SPEC = importlib.util.spec_from_file_location("native_qt_manage", SCRIPT)
assert SPEC and SPEC.loader
MANAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MANAGE)


class NativeQtProfileTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        tokens = root / "graphite.json"
        source_tokens = json.loads((ROOT / "out/preview/graphite.json").read_text())
        tokens.write_text(json.dumps(source_tokens))
        bases = root / "bases"
        for mode, base in MANAGE.BASES.items():
            directory = bases / base
            directory.mkdir(parents=True)
            (directory / f"{base}.kvconfig").write_text(
                "[%General]\nauthor=upstream\n[GeneralColors]\nwindow.color=#222222\n"
                "[GenericFrame]\nframe.top=2\n[PanelButtonCommand]\nmin_height=20\n"
            )
            (directory / f"{base}.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect id="button" fill="#222222" '
                'stroke="#3daee9" width="40" height="40" rx="8"/>'
                '<rect id="surface" fill="#ffffff" width="40" height="40"/></svg>\n'
            )
        dolphin_desktop = root / "org.kde.dolphin.desktop"
        dolphin_desktop.write_text("[Desktop Entry]\nName=Dolphin\nExec=dolphin %u\n")
        return tokens, bases, root / "generated", dolphin_desktop

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True, check=False
        )

    def test_plan_generates_two_semantic_themes_and_qt_palettes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tokens, bases, output, dolphin_desktop = self.make_fixture(root)
            home = root / "home"
            result = self.run_cli(
                "--tokens", str(tokens), "--kvantum-root", str(bases),
                "--output", str(output), "--home", str(home),
                "--dolphin-desktop", str(dolphin_desktop),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no live files changed", result.stdout)
            self.assertFalse((home / ".config").exists())
            dark_config = output / "Kvantum/ShadcnGraphiteDark/ShadcnGraphiteDark.kvconfig"
            text = dark_config.read_text()
            self.assertIn("min_height=40", text)
            self.assertIn("frame.top=8", text)
            self.assertIn("frame.top=12", text)
            self.assertIn("controls 8px; cards 12px", text)
            self.assertIn("window.color=#1b1b1b", text)
            self.assertIn("highlight.color=#a1a1a1", text)
            parser = MANAGE.config_parser()
            parser.read(dark_config)
            self.assertEqual(parser["%General"]["respect_DE"], "false")
            self.assertNotIn("respect_DE", parser["Hacks"])
            self.assertIn("transparent_dolphin_view=false", text)
            self.assertTrue((output / "qt5ct/colors/shadcn-graphite-light.conf").is_file())
            self.assertTrue((output / "qt6ct/colors/shadcn-graphite-dark.conf").is_file())
            palette = (output / "qt5ct/colors/shadcn-graphite-dark.conf").read_text()
            self.assertEqual(palette.count("_colors="), 3)
            self.assertEqual(len(palette.splitlines()[1].split("=" , 1)[1].split(",")), 21)
            svg = (output / "Kvantum/ShadcnGraphiteDark/ShadcnGraphiteDark.svg").read_text()
            self.assertIn("#232323", svg)
            self.assertIn("#a1a1a1", svg)
            self.assertNotIn("#3daee9", svg.lower())
            light_svg = (output / "Kvantum/ShadcnGraphiteLight/ShadcnGraphiteLight.svg").read_text()
            self.assertIn('id="surface" fill="#f2f2f2"', light_svg)

            stale = output / "Kvantum/Stale/Stale.svg"
            stale.parent.mkdir(parents=True)
            stale.write_text("not managed")
            planned = MANAGE.managed_files(output, home, "dark", tokens, dolphin_desktop)
            self.assertFalse(any(path.name == "Stale.svg" for path in planned))
            kdeglobals = planned[home / ".config/kdeglobals"].decode()
            self.assertIn("BackgroundNormal=27,27,27", kdeglobals)
            self.assertIn("ForegroundNormal=219,219,219", kdeglobals)
            dark_scheme = planned[home / ".local/share/color-schemes/ShadcnGraphiteDark.colors"].decode()
            self.assertIn("Name=ShadcnGraphiteDark", dark_scheme)
            qss = planned[home / ".config/shadcn-theme-forge/qt/dolphin.qss"].decode()
            self.assertIn('QToolButton[popupMode="0"]::menu-indicator', qss)
            desktop = planned[home / ".local/share/applications/org.kde.dolphin.desktop"].decode()
            self.assertIn("Exec=dolphin -stylesheet", desktop)
            self.assertIn(str(home / ".config/shadcn-theme-forge/qt/dolphin.qss"), desktop)

    def test_apply_verify_and_exact_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tokens, bases, output, dolphin_desktop = self.make_fixture(root)
            home = root / "home"
            old = home / ".config/Kvantum/kvantum.kvconfig"
            old.parent.mkdir(parents=True)
            old.write_text("[General]\ntheme=Existing\n")
            common = (
                "--tokens", str(tokens), "--kvantum-root", str(bases),
                "--output", str(output), "--home", str(home),
                "--dolphin-desktop", str(dolphin_desktop),
            )
            applied = self.run_cli(*common, "--mode", "light", "--apply")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertIn("theme=ShadcnGraphiteLight", old.read_text())
            self.assertEqual(self.run_cli("--home", str(home), "--verify").returncode, 0)
            duplicate = self.run_cli(*common, "--apply")
            self.assertEqual(duplicate.returncode, 2)
            rolled_back = self.run_cli("--home", str(home), "--rollback")
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            self.assertEqual(old.read_text(), "[General]\ntheme=Existing\n")
            self.assertFalse((home / MANAGE.STATE_RELATIVE).exists())
            self.assertFalse((home / ".config/Kvantum/ShadcnGraphiteDark/ShadcnGraphiteDark.svg").exists())
            self.assertFalse((home / ".config/Kvantum/ShadcnGraphiteLight/ShadcnGraphiteLight.svg").exists())

    def test_verify_and_rollback_fail_closed_after_user_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tokens, bases, output, dolphin_desktop = self.make_fixture(root)
            home = root / "home"
            common = (
                "--tokens", str(tokens), "--kvantum-root", str(bases),
                "--output", str(output), "--home", str(home), "--apply",
                "--dolphin-desktop", str(dolphin_desktop),
            )
            self.assertEqual(self.run_cli(*common).returncode, 0)
            config = home / ".config/qt5ct/qt5ct.conf"
            config.write_text(config.read_text() + "# user edit\n")
            self.assertEqual(self.run_cli("--home", str(home), "--verify").returncode, 2)
            self.assertEqual(self.run_cli("--home", str(home), "--rollback").returncode, 2)
            self.assertTrue(config.read_text().endswith("# user edit\n"))

    def test_missing_upstream_base_fails_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tokens = root / "tokens.json"
            tokens.write_bytes((ROOT / "out/preview/graphite.json").read_bytes())
            output = root / "output"
            result = self.run_cli(
                "--tokens", str(tokens), "--kvantum-root", str(root / "missing"),
                "--output", str(output), "--home", str(root / "home"), "--apply",
                "--dolphin-desktop", str(root / "org.kde.dolphin.desktop"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertFalse((root / "home").exists())


if __name__ == "__main__":
    unittest.main()

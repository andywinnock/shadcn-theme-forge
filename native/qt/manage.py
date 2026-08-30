#!/usr/bin/env python3
"""Generate and safely install the shadcn Graphite Qt/Kvantum profile."""

from __future__ import annotations

import argparse
import base64
import configparser
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOKENS = ROOT / "out/preview/graphite.json"
DEFAULT_OUTPUT = ROOT / "out/native/qt/generated"
DEFAULT_KVANTUM_ROOT = Path("/usr/share/Kvantum")
DEFAULT_DOLPHIN_DESKTOP = Path("/usr/share/applications/org.kde.dolphin.desktop")
STATE_RELATIVE = Path(".local/state/shadcn-theme-forge/qt/transaction.json")
THEMES = {"dark": "ShadcnGraphiteDark", "light": "ShadcnGraphiteLight"}
BASES = {"dark": "KvMojave", "light": "KvMojaveLight"}
CONTROL_SECTIONS = (
    "PanelButtonCommand",
    "ToolbarButton",
    "ToolbarLineEdit",
    "IndicatorSpinBox",
    "LineEdit",
    "ComboBox",
)
COLOR_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b")

DOLPHIN_QSS = b'''/* Keep history menus available without decorating ordinary navigation buttons. */
QToolButton[popupMode="0"]::menu-indicator {
    image: none;
    width: 0px;
    height: 0px;
}
'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rgb(color: str) -> tuple[int, int, int]:
    value = color.removeprefix("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def qt_color(color: str, alpha: str = "ff") -> str:
    return f"#{alpha}{color.removeprefix('#').lower()}"


def rgb_csv(color: str) -> str:
    return ",".join(str(channel) for channel in rgb(color))


def remap_svg(source: str, colors: dict[str, str], mode: str) -> str:
    """Map the upstream base's literal colors onto semantic Graphite roles."""

    def replacement(match: re.Match[str]) -> str:
        red, green, blue = rgb(match.group(0))
        spread = max(red, green, blue) - min(red, green, blue)
        luminance = (red * 299 + green * 587 + blue * 114) // 1000
        if spread > 42:
            role = "error" if red > green * 1.25 and red > blue * 1.25 else "primary"
        elif mode == "light" and luminance < 34:
            role = "on_surface"
        elif mode == "light" and luminance < 72:
            role = "on_surface_variant"
        elif mode == "light" and luminance < 116:
            role = "outline"
        elif mode == "light" and luminance < 184:
            role = "surface_container_highest"
        elif mode == "light" and luminance < 230:
            role = "surface_container"
        elif mode == "light":
            role = "surface"
        elif luminance < 34:
            role = "surface_container_low"
        elif luminance < 72:
            role = "surface_container"
        elif luminance < 116:
            role = "outline"
        elif luminance < 184:
            role = "on_surface_variant"
        else:
            role = "on_surface"
        return colors[role]

    return COLOR_RE.sub(replacement, source)


class CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def config_parser() -> configparser.ConfigParser:
    return CaseSensitiveConfigParser(interpolation=None, strict=False)


def kvconfig(source: Path, colors: dict[str, str], theme: str, base: str) -> str:
    parser = config_parser()
    parser.read(source, encoding="utf-8")
    general = parser["%General"]
    general["author"] = "shadcn-theme-forge (derived from Tsu Jan's installed Kvantum base)"
    general["comment"] = f"shadcn Graphite component profile; upstream base: {base}"
    general["scroll_width"] = "12"
    general["slider_handle_width"] = "16"
    general["slider_handle_length"] = "16"
    general["check_size"] = "16"
    general["animate_states"] = "true"
    general["menu_shadow_depth"] = "8"
    general["tooltip_shadow_depth"] = "8"
    general["respect_DE"] = "false"

    # Niri has no KDE session palette. Letting Kvantum respect a stale ambient
    # kdeglobals can produce dark text on the dark forge surface, so the
    # generated semantic palette must remain authoritative.
    if not parser.has_section("Hacks"):
        parser.add_section("Hacks")
    hacks = parser["Hacks"]
    hacks["respect_darkness"] = "true"
    hacks["transparent_dolphin_view"] = "false"
    hacks["transparent_pcmanfm_view"] = "false"
    hacks["transparent_pcmanfm_sidepane"] = "false"

    roles = parser["GeneralColors"]
    roles.update(
        {
            "window.color": colors["surface"],
            "inactive.window.color": colors["surface_container_low"],
            "base.color": colors["surface_container_lowest"],
            "inactive.base.color": colors["surface_container_lowest"],
            "alt.base.color": colors["surface_container"],
            "inactive.alt.base.color": colors["surface_container"],
            "button.color": colors["surface_container_high"],
            "light.color": colors["surface_container_highest"],
            "mid.light.color": colors["surface_container_high"],
            "dark.color": colors["surface_container_low"],
            "mid.color": colors["outline"],
            "highlight.color": colors["primary"],
            "inactive.highlight.color": colors["hover"],
            "tooltip.base.color": colors["surface_container_high"],
            "text.color": colors["on_surface"],
            "inactive.text.color": colors["on_surface_variant"],
            "window.text.color": colors["on_surface"],
            "inactive.window.text.color": colors["on_surface_variant"],
            "button.text.color": colors["on_surface"],
            "disabled.text.color": colors["on_surface_variant"],
            "tooltip.text.color": colors["on_surface"],
            "highlight.text.color": colors["on_primary"],
            "inactive.highlight.text.color": colors["on_hover"],
            "link.color": colors["tertiary"],
            "link.visited.color": colors["secondary"],
        }
    )
    for section in CONTROL_SECTIONS:
        if not parser.has_section(section):
            parser.add_section(section)
        parser[section]["min_height"] = "40"
        parser[section]["text.margin.left"] = "8"
        parser[section]["text.margin.right"] = "8"
        parser[section]["frame.top"] = "8"
        parser[section]["frame.bottom"] = "8"
        parser[section]["frame.left"] = "8"
        parser[section]["frame.right"] = "8"

    parser["GenericFrame"]["frame.top"] = "12"
    parser["GenericFrame"]["frame.bottom"] = "12"
    parser["GenericFrame"]["frame.left"] = "12"
    parser["GenericFrame"]["frame.right"] = "12"

    from io import StringIO

    stream = StringIO()
    stream.write(f"# Generated theme: {theme}\n# Component radii: controls 8px; cards 12px (SVG geometry from {base}).\n")
    parser.write(stream, space_around_delimiters=False)
    return stream.getvalue()


def palette(colors: dict[str, str]) -> str:
    # Qt's 21 QPalette roles: WindowText, Button, Light, Midlight, Dark, Mid,
    # Text, BrightText, ButtonText, Base, Window, Shadow, Highlight,
    # HighlightedText, Link, LinkVisited, AlternateBase, NoRole, ToolTipBase,
    # ToolTipText, PlaceholderText.
    active = (
        colors["on_surface"], colors["surface_container_high"], colors["surface_container_highest"],
        colors["surface_container_high"], colors["surface_container_low"], colors["outline"],
        colors["on_surface"], colors["on_primary"], colors["on_surface"],
        colors["surface_container_lowest"], colors["surface"], colors["shadow"],
        colors["primary"], colors["on_primary"], colors["tertiary"], colors["secondary"],
        colors["surface_container"], colors["on_surface"], colors["surface_container_high"],
        colors["on_surface"], colors["on_surface_variant"],
    )
    inactive = active
    disabled = list(active)
    for index in (0, 6, 8, 13, 19, 20):
        disabled[index] = colors["on_surface_variant"]

    def line(name: str, values: tuple[str, ...] | list[str]) -> str:
        return f"{name}=" + ", ".join(qt_color(value, "80" if index == 20 else "ff") for index, value in enumerate(values))

    return "[ColorScheme]\n" + "\n".join(
        (line("active_colors", active), line("disabled_colors", disabled), line("inactive_colors", inactive))
    ) + "\n"


def kde_color_scheme(colors: dict[str, str], theme: str) -> bytes:
    parser = config_parser()
    section_roles = {
        "Colors:Window": ("surface", "surface_container", "on_surface"),
        "Colors:View": ("surface_container_lowest", "surface_container", "on_surface"),
        "Colors:Button": ("surface_container_high", "surface_container", "on_surface"),
        "Colors:Header": ("surface_container", "surface_container_low", "on_surface"),
        "Colors:Header][Inactive": ("surface_container_low", "surface", "on_surface_variant"),
        "Colors:Tooltip": ("surface_container_high", "surface_container", "on_surface"),
    }
    for section, (background, alternate, foreground) in section_roles.items():
        parser.add_section(section)
        parser[section].update(
            {
                "BackgroundNormal": rgb_csv(colors[background]),
                "BackgroundAlternate": rgb_csv(colors[alternate]),
                "ForegroundNormal": rgb_csv(colors[foreground]),
                "ForegroundInactive": rgb_csv(colors["on_surface_variant"]),
                "DecorationFocus": rgb_csv(colors["primary"]),
                "DecorationHover": rgb_csv(colors["primary"]),
            }
        )
    parser.add_section("Colors:Selection")
    parser["Colors:Selection"].update(
        {
            "BackgroundNormal": rgb_csv(colors["primary"]),
            "BackgroundAlternate": rgb_csv(colors["surface_container"]),
            "ForegroundNormal": rgb_csv(colors["on_primary"]),
            "ForegroundInactive": rgb_csv(colors["on_surface_variant"]),
            "DecorationFocus": rgb_csv(colors["primary"]),
            "DecorationHover": rgb_csv(colors["primary"]),
        }
    )
    parser.add_section("General")
    parser["General"].update({"ColorScheme": theme, "Name": theme})
    from io import StringIO
    stream = StringIO()
    parser.write(stream, space_around_delimiters=False)
    return stream.getvalue().encode()


def generate(tokens_path: Path, output: Path, kvantum_root: Path) -> dict[Path, bytes]:
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    if set(tokens) != {"dark", "light"}:
        raise ValueError("token file must contain exactly dark and light modes")
    files: dict[Path, bytes] = {}
    theme_attribution: dict[str, dict[str, str]] = {}
    for mode in ("dark", "light"):
        colors = tokens[mode]
        required = {
            "primary", "on_primary", "secondary", "tertiary", "error", "surface", "on_surface",
            "on_surface_variant", "outline", "shadow", "hover", "on_hover", "surface_container_lowest",
            "surface_container_low", "surface_container", "surface_container_high", "surface_container_highest",
        }
        missing = required.difference(colors)
        if missing:
            raise ValueError(f"{mode} tokens missing: {', '.join(sorted(missing))}")
        theme, base = THEMES[mode], BASES[mode]
        base_dir = kvantum_root / base
        base_config, base_svg = base_dir / f"{base}.kvconfig", base_dir / f"{base}.svg"
        if not base_config.is_file() or not base_svg.is_file():
            raise FileNotFoundError(f"installed Kvantum base is incomplete: {base_dir}")
        theme_dir = output / "Kvantum" / theme
        files[theme_dir / f"{theme}.kvconfig"] = kvconfig(base_config, colors, theme, base).encode()
        files[theme_dir / f"{theme}.svg"] = remap_svg(
            base_svg.read_text(encoding="utf-8"), colors, mode
        ).encode()
        palette_data = palette(colors).encode()
        palette_name = f"shadcn-graphite-{mode}.conf"
        files[output / "qt5ct/colors" / palette_name] = palette_data
        files[output / "qt6ct/colors" / palette_name] = palette_data
        theme_attribution[mode] = {
            "name": theme,
            "base": base,
            "base_config": str(base_config),
            "base_svg": str(base_svg),
        }
    attribution = {"tokens": str(tokens_path.resolve()), "themes": theme_attribution}
    files[output / "manifest.json"] = (json.dumps(attribution, indent=2, sort_keys=True) + "\n").encode()
    for path, data in files.items():
        atomic_write(path, data)
    return files


def dolphin_desktop_entry(source: Path, stylesheet: Path) -> bytes:
    text = source.read_text(encoding="utf-8")
    original = "Exec=dolphin %u"
    replacement = f"Exec=dolphin -stylesheet {stylesheet} %u"
    if text.count(original) != 1:
        raise ValueError(f"unexpected Dolphin desktop entry: {source}")
    return text.replace(original, replacement, 1).encode()


def managed_files(
    output: Path,
    home: Path,
    mode: str,
    tokens: Path = DEFAULT_TOKENS,
    dolphin_desktop: Path = DEFAULT_DOLPHIN_DESKTOP,
) -> dict[Path, bytes]:
    theme = THEMES[mode]
    all_colors = json.loads(tokens.read_text())
    colors = all_colors[mode]
    result: dict[Path, bytes] = {}
    for generated_theme in THEMES.values():
        for suffix in ("kvconfig", "svg"):
            source = output / "Kvantum" / generated_theme / f"{generated_theme}.{suffix}"
            result[home / ".config/Kvantum" / generated_theme / source.name] = source.read_bytes()
    for toolkit in ("qt5ct", "qt6ct"):
        for palette_mode in ("dark", "light"):
            source = output / toolkit / "colors" / f"shadcn-graphite-{palette_mode}.conf"
            result[home / ".config" / toolkit / "colors" / source.name] = source.read_bytes()
        config_path = home / ".config" / toolkit / f"{toolkit}.conf"
        parser = config_parser()
        if config_path.exists():
            parser.read(config_path, encoding="utf-8")
        if not parser.has_section("Appearance"):
            parser.add_section("Appearance")
        parser["Appearance"]["style"] = "kvantum"
        parser["Appearance"]["custom_palette"] = "true"
        parser["Appearance"]["color_scheme_path"] = str(
            home / ".config" / toolkit / "colors" / f"shadcn-graphite-{mode}.conf"
        )
        from io import StringIO
        stream = StringIO()
        parser.write(stream, space_around_delimiters=False)
        result[config_path] = stream.getvalue().encode()
    for scheme_mode, scheme_theme in THEMES.items():
        result[home / ".local/share/color-schemes" / f"{scheme_theme}.colors"] = kde_color_scheme(
            all_colors[scheme_mode], scheme_theme
        )
    kvantum_config = home / ".config/Kvantum/kvantum.kvconfig"
    parser = config_parser()
    if kvantum_config.exists():
        parser.read(kvantum_config, encoding="utf-8")
    if not parser.has_section("General"):
        parser.add_section("General")
    parser["General"]["theme"] = theme
    from io import StringIO
    stream = StringIO()
    parser.write(stream, space_around_delimiters=False)
    result[kvantum_config] = stream.getvalue().encode()

    # KDE Frameworks applications (including Dolphin) resolve KColorScheme
    # roles from kdeglobals even while Kvantum owns widget rendering. Manage
    # both sources transactionally so foregrounds cannot drift from surfaces.
    kdeglobals = home / ".config/kdeglobals"
    parser = config_parser()
    if kdeglobals.exists():
        parser.read(kdeglobals, encoding="utf-8")
    section_roles = {
        "Colors:Window": ("surface", "surface_container", "on_surface"),
        "Colors:View": ("surface_container_lowest", "surface_container", "on_surface"),
        "Colors:Button": ("surface_container_high", "surface_container", "on_surface"),
        "Colors:Header": ("surface_container", "surface_container_low", "on_surface"),
        "Colors:Header][Inactive": ("surface_container_low", "surface", "on_surface_variant"),
        "Colors:Tooltip": ("surface_container_high", "surface_container", "on_surface"),
    }
    for section, (background, alternate, foreground) in section_roles.items():
        if not parser.has_section(section):
            parser.add_section(section)
        values = parser[section]
        values["BackgroundNormal"] = rgb_csv(colors[background])
        values["BackgroundAlternate"] = rgb_csv(colors[alternate])
        values["ForegroundNormal"] = rgb_csv(colors[foreground])
        values["ForegroundInactive"] = rgb_csv(colors["on_surface_variant"])
        values["DecorationFocus"] = rgb_csv(colors["primary"])
        values["DecorationHover"] = rgb_csv(colors["primary"])
    if not parser.has_section("Colors:Selection"):
        parser.add_section("Colors:Selection")
    parser["Colors:Selection"].update(
        {
            "BackgroundNormal": rgb_csv(colors["primary"]),
            "BackgroundAlternate": rgb_csv(colors["surface_container"]),
            "ForegroundNormal": rgb_csv(colors["on_primary"]),
            "ForegroundInactive": rgb_csv(colors["on_surface_variant"]),
            "DecorationFocus": rgb_csv(colors["primary"]),
            "DecorationHover": rgb_csv(colors["primary"]),
        }
    )
    if not parser.has_section("General"):
        parser.add_section("General")
    parser["General"]["ColorScheme"] = theme
    parser["General"].pop("ColorSchemeHash", None)
    if not parser.has_section("KDE"):
        parser.add_section("KDE")
    parser["KDE"]["widgetStyle"] = "kvantum"
    stream = StringIO()
    parser.write(stream, space_around_delimiters=False)
    result[kdeglobals] = stream.getvalue().encode()

    dolphin_qss = home / ".config/shadcn-theme-forge/qt/dolphin.qss"
    result[dolphin_qss] = DOLPHIN_QSS
    result[home / ".local/share/applications/org.kde.dolphin.desktop"] = dolphin_desktop_entry(
        dolphin_desktop, dolphin_qss
    )
    return result


def apply(files: dict[Path, bytes], home: Path, mode: str) -> None:
    state_path = home / STATE_RELATIVE
    if state_path.exists():
        raise RuntimeError(f"active Qt transaction exists; verify or rollback first: {state_path}")
    records = []
    for path, data in files.items():
        before = path.read_bytes() if path.exists() else None
        records.append(
            {
                "path": str(path),
                "before": None if before is None else base64.b64encode(before).decode("ascii"),
                "after_sha256": sha256(data),
            }
        )
    transaction = {"version": 1, "mode": mode, "files": records}
    atomic_write(state_path, (json.dumps(transaction, indent=2, sort_keys=True) + "\n").encode())
    try:
        for path, data in files.items():
            atomic_write(path, data)
    except Exception:
        rollback(home, require_hash=False)
        raise


def load_state(home: Path) -> tuple[Path, dict[str, Any]]:
    state_path = home / STATE_RELATIVE
    if not state_path.is_file():
        raise RuntimeError(f"no active Qt transaction: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("version") != 1 or not isinstance(state.get("files"), list):
        raise RuntimeError("invalid Qt transaction journal")
    home_root = home.resolve()
    for record in state["files"]:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise RuntimeError("invalid file record in Qt transaction journal")
        try:
            Path(record["path"]).resolve().relative_to(home_root)
        except ValueError as error:
            raise RuntimeError("Qt transaction contains a path outside the selected home") from error
    return state_path, state


def verify(home: Path) -> None:
    _, state = load_state(home)
    failures = []
    for record in state["files"]:
        path = Path(record["path"])
        if not path.is_file() or sha256(path.read_bytes()) != record["after_sha256"]:
            failures.append(str(path))
    if failures:
        raise RuntimeError("managed Qt files differ from the applied plan:\n" + "\n".join(failures))


def rollback(home: Path, require_hash: bool = True) -> None:
    state_path, state = load_state(home)
    if require_hash:
        verify(home)
    for record in reversed(state["files"]):
        path = Path(record["path"])
        before = record["before"]
        if before is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, base64.b64decode(before))
    state_path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="install the generated profile with a rollback journal")
    action.add_argument("--verify", action="store_true", help="verify the currently applied transaction")
    action.add_argument("--rollback", action="store_true", help="restore the exact pre-apply state")
    parser.add_argument("--mode", choices=("dark", "light"), default="dark")
    parser.add_argument("--tokens", type=Path, default=DEFAULT_TOKENS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--kvantum-root", type=Path, default=DEFAULT_KVANTUM_ROOT)
    parser.add_argument("--dolphin-desktop", type=Path, default=DEFAULT_DOLPHIN_DESKTOP)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args(argv)
    try:
        if args.verify:
            verify(args.home)
            print("Qt/Kvantum transaction verified")
            return 0
        if args.rollback:
            rollback(args.home)
            print("Qt/Kvantum transaction rolled back")
            return 0
        generated = generate(args.tokens, args.output, args.kvantum_root)
        planned = managed_files(args.output, args.home, args.mode, args.tokens, args.dolphin_desktop)
        print(f"generated {len(generated)} files in {args.output}")
        print(f"plan: {args.mode} -> {len(planned)} managed files under {args.home}")
        for path in sorted(planned):
            print(path)
        if args.apply:
            apply(planned, args.home, args.mode)
            verify(args.home)
            print("Qt/Kvantum profile applied and verified")
        else:
            print("no live files changed; rerun with --apply to activate")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

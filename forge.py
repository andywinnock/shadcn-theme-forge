#!/usr/bin/env python3
"""shadcn-theme-forge: compile tweakcn shadcn presets into native theme files.

Sources:
  https://tweakcn.com/r/registry.json   (official shadcn registry schema, MIT)

Outputs per preset:
  ~/.config/noctalia/palettes/<name>.json   noctalia native palette
  out/css/tweakcn/<name>.css                theme-independent CSS variables
  out/index.json                            manifest for later adapters (gtk.css, ...)

Usage:
  python3 forge.py                      # all presets
  python3 forge.py --only modern-minimal,graphite
  python3 forge.py --noctalia-dir DIR   # sandbox palettes dir (default: real config)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.request
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from oklch import css_color_to_hex  # noqa: E402

REGISTRY_URL = "https://tweakcn.com/r/registry.json"
DEFAULT_PALETTE_DIR = Path.home() / ".config" / "noctalia" / "palettes"
OUT_DIR = Path(__file__).parent / "out"
CACHE = Path(__file__).parent / "registry.json"


def load_registry(*, write_cache: bool = True) -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    with urllib.request.urlopen(REGISTRY_URL, timeout=20) as r:
        data = json.loads(r.read().decode())
    if write_cache:
        CACHE.write_text(json.dumps(data))
    return data


def opaque(hexv: str | None) -> str | None:
    """Noctalia's palette parser (Color::fromHex) requires exactly #RRGGBB."""
    if not hexv:
        return hexv
    c = hexv.lstrip("#")
    if len(c) == 8:
        return "#" + c[:6]
    if len(c) == 3:
        return "#" + "".join(ch * 2 for ch in c)
    return "#" + c


def _contrast_ratio(hex1: str, hex2: str) -> float:
    def lum(h: str) -> float:
        c = h.lstrip("#")
        rs = [int(c[i:i+2], 16) / 255 for i in (0, 2, 4)]
        f = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rs]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]

    l1, l2 = sorted((lum(hex1), lum(hex2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def on_color(bg: str | None) -> str:
    """Pick white or black text for `bg` by WCAG contrast."""
    if not bg:
        return "#ffffff"
    return "#ffffff" if _contrast_ratio(bg, "#ffffff") >= _contrast_ratio(bg, "#000000") else "#000000"


def pick(tokens: dict, *keys: str) -> str | None:
    for k in keys:
        v = tokens.get(k)
        if v:
            return css_color_to_hex(v)
    return None


def map_mode(tokens: dict) -> dict:
    """shadcn cssVars mode -> noctalia palette role dict (hex strings)."""
    primary = pick(tokens, "primary")
    accent = pick(tokens, "accent")
    background = pick(tokens, "background")
    foreground = pick(tokens, "foreground")
    muted = pick(tokens, "muted")
    muted_fg = pick(tokens, "muted-foreground")
    destructive = pick(tokens, "destructive")
    ring = pick(tokens, "ring")
    border = pick(tokens, "border")
    shadow_color = pick(tokens, "shadow-color", "shadow")
    if shadow_color is None and any(tokens.get(key) for key in ("shadow-color", "shadow")):
        warnings.warn(
            "unsupported shadow-color value; using background as the shadow fallback",
            RuntimeWarning,
            stacklevel=2,
        )
    chart2 = pick(tokens, "chart-2")
    accent_fg = pick(tokens, "accent-foreground") or on_color(accent)
    return {
        "primary": primary,
        "onPrimary": pick(tokens, "primary-foreground") or on_color(primary),
        "secondary": ring or primary,           # mapping.md note 1
        "onSecondary": pick(tokens, "ring-foreground", "primary-foreground") or on_color(ring or primary),
        "tertiary": chart2 or accent or primary,
        "onTertiary": pick(tokens, "chart-2-foreground") or on_color(chart2 or accent),
        "error": destructive,
        "onError": pick(tokens, "destructive-foreground") or on_color(destructive),
        "surface": background,
        "onSurface": foreground,
        "surfaceVariant": muted,
        "onSurfaceVariant": muted_fg or on_color(muted),
        "outline": border,
        "shadow": shadow_color or background,
        "hover": accent or muted,               # mapping.md: shadcn hover = accent surface
        "onHover": accent_fg,
    }


def terminal_mode(tokens: dict, palette: dict) -> dict:
    """Derive a terminal palette so noctalia accepts the file (dark/light)."""
    fg = palette["onSurface"] or "#d4d4d8"
    bg = palette["surface"] or "#18181b"
    c1 = palette["error"] or "#ef4444"
    c2 = pick(tokens, "chart-2") or palette["tertiary"] or "#22c55e"
    c3 = pick(tokens, "chart-3") or palette["primary"] or "#3b82f6"
    c4 = pick(tokens, "chart-4") or "#eab308"
    c5 = pick(tokens, "chart-5") or palette["secondary"] or "#a855f7"
    c6 = palette["secondary"] or "#ec4899"
    neutral = palette["outline"] or "#3f3f46"
    return {
        "normal": {
            "black": palette["shadow"] or bg,
            "red": c1,
            "green": c2,
            "yellow": c4,
            "blue": c3,
            "magenta": c5,
            "cyan": c6,
            "white": fg,
        },
        "bright": {
            "black": neutral,
            "red": c1,
            "green": c2,
            "yellow": c4,
            "blue": c3,
            "magenta": c5,
            "cyan": c6,
            "white": fg,
        },
        "foreground": fg,
        "background": bg,
        "cursor": palette["primary"] or fg,
        "cursorText": palette["onPrimary"] or bg,
        "selectionFg": palette["onPrimary"] or bg,
        "selectionBg": palette["primary"] or neutral,
    }


def noctalia_palette(item: dict) -> dict:
    modes: dict[str, dict[str, object]] = {}
    for mode in ("dark", "light"):
        tokens = item.get("cssVars", {}).get(mode)
        if not tokens:
            continue
        palette_roles = {k: opaque(v) for k, v in map_mode(tokens).items()}
        terminal = terminal_mode(tokens, palette_roles)
        pal: dict[str, object] = dict(palette_roles)
        pal["terminal"] = {
            "normal": {k: opaque(v) for k, v in terminal["normal"].items()},
            "bright": {k: opaque(v) for k, v in terminal["bright"].items()},
            **{k: opaque(v) for k, v in terminal.items()
               if k not in ("normal", "bright")},
        }
        modes[mode] = pal
    if "dark" not in modes and "light" not in modes:
        raise ValueError(f"{item['name']}: no cssVars modes")
    if "light" not in modes:
        modes["light"] = copy.deepcopy(modes["dark"])
    if "dark" not in modes:
        modes["dark"] = copy.deepcopy(modes["light"])
    return modes


def web_mode_tokens(item: dict) -> dict[str, dict[str, str]]:
    """Return effective web tokens after applying the real CSS mode cascade.

    tweakcn's ``theme`` tokens are shared. Light mode adds its declarations;
    dark mode inherits that root result, then applies its own overrides.
    """
    css_vars = item.get("cssVars", {})
    shared = dict(css_vars.get("theme") or {})
    light = {**shared, **(css_vars.get("light") or {})}
    dark = {**light, **(css_vars.get("dark") or {})}
    return {"light": light, "dark": dark}


def css_text(item: dict) -> str:
    """Theme-independent CSS variables for web/CSS consumers (no noctalia)."""
    modes = web_mode_tokens(item)
    lines = [
        f"/* {item['title']} — shadcn/tweakcn preset, generated by shadcn-theme-forge */",
        "@layer base {",
    ]
    if modes["light"]:
        lines.append("  :root {")
        for k, v in modes["light"].items():
            lines.append(f"    --{k}: {v};")
        lines.append("  }")
    dark_overrides = {
        key: value
        for key, value in modes["dark"].items()
        if modes["light"].get(key) != value
    }
    if dark_overrides:
        lines.append("  .dark, [data-theme=dark] {")
        for k, v in dark_overrides.items():
            lines.append(f"    --{k}: {v};")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated preset names")
    ap.add_argument("--noctalia-dir", default=None,
                    help=f"palette dir (default: {DEFAULT_PALETTE_DIR})")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    reg = load_registry(write_cache=not args.dry_run)
    only = set(args.only.split(",")) if args.only else None
    palette_dir = Path(args.noctalia_dir) if args.noctalia_dir else DEFAULT_PALETTE_DIR
    if not args.dry_run:
        (OUT_DIR / "css" / "tweakcn").mkdir(parents=True, exist_ok=True)

    manifest = []
    for item in reg.get("items", []):
        name = item["name"]
        if only and name not in only:
            continue
        pal = noctalia_palette(item)
        css = css_text(item)
        entry = {"name": name, "title": item.get("title", name),
                 "description": item.get("description", "")}
        manifest.append(entry)
        if args.dry_run:
            print(f"[dry] {name}: {len(pal)} modes, css {len(css)}b")
            continue
        palette_dir.mkdir(parents=True, exist_ok=True)
        (palette_dir / f"{name}.json").write_text(json.dumps(pal, indent=2))
        (OUT_DIR / "css" / "tweakcn" / f"{name}.css").write_text(css)
        print(f"forge: {name:24} -> palettes/{name}.json + css")

    if args.dry_run:
        noun = "theme" if len(manifest) == 1 else "themes"
        print(f"\n{len(manifest)} {noun} selected; no files written")
    else:
        (OUT_DIR / "index.json").write_text(json.dumps({"themes": manifest}, indent=2))
        print(f"\n{len(manifest)} themes forged -> {palette_dir} and {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

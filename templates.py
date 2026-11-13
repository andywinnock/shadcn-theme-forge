#!/usr/bin/env python3
"""Template-layer generation + offline preview harness for shadcn-theme-forge.

Emits, per preset:
  out/preview/<name>.json   `noctalia theme --theme-json` input: snake_case token
                            map (role table + flattened terminal_* tokens)
And once per forge:
  out/templates/gtk3.css    shadcn-flavored GTK3 template ({{ colors.* }} vocabulary)
  out/templates/gtk4.css    GTK4 variant
  out/templates/templates.toml  user-template manifest for [theme.templates.user]

Preview workflow (no display server, no running shell):
  python3 templates.py                      # regenerate preview maps + templates
  noctalia theme --theme-json out/preview/<name>.json \
      -r out/templates/gtk3.css /tmp/x.css  # render any template against any preset
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent))
from forge import DEFAULT_PALETTE_DIR, OUT_DIR, load_registry, noctalia_palette  # noqa: E402

TEMPLATES_DIR = OUT_DIR / "templates"
PREVIEW_DIR = OUT_DIR / "preview"

# camelCase palette roles -> noctalia template token names (Material3 snake_case).
ROLE_TO_TOKEN = {
    "primary": "primary",
    "onPrimary": "on_primary",
    "secondary": "secondary",
    "onSecondary": "on_secondary",
    "tertiary": "tertiary",
    "onTertiary": "on_tertiary",
    "error": "error",
    "onError": "on_error",
    "surface": "surface",
    "onSurface": "on_surface",
    "surfaceVariant": "surface_variant",
    "onSurfaceVariant": "on_surface_variant",
    "outline": "outline",
    "shadow": "shadow",
    "hover": "hover",
    "onHover": "on_hover",
}

TERMINAL_TOKENS = {
    "foreground": "terminal_foreground",
    "background": "terminal_background",
    "cursor": "terminal_cursor",
    "cursorText": "terminal_cursor_text",
    "selectionFg": "terminal_selection_fg",
    "selectionBg": "terminal_selection_bg",
}

# Composite surface roles a user template may reference; synthesized between
# surface and surfaceVariant (L-interpolated). Empirically chosen to match what
# stock noctalia templates expect (gtk3.css uses surface_container).
CONTAINER_LEVELS = {
    "surface_container_lowest": 0.0,
    "surface_container_low": 0.25,
    "surface_container": 0.5,
    "surface_container_high": 0.75,
    "surface_container_highest": 1.0,
}

ALIASES = {
    "background": "surface",
    "on_background": "on_surface",
    "outline_variant": "surface_variant",
    "scrim": "shadow",
}


def _mix_rgb(hex_a: str, hex_b: str, t: float) -> str:
    a = hex_a.lstrip("#")
    b = hex_b.lstrip("#")
    ca = [int(a[i:i+2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i+2], 16) for i in (0, 2, 4)]
    mixed = [round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def theme_json(pal: dict) -> dict:
    """Convert a noctalia palette (camelCase) to a --theme-json token map."""
    out: dict = {}
    for mode in ("dark", "light"):
        src = pal.get(mode)
        if not src:
            continue
        tok: dict = {}
        for role, token in ROLE_TO_TOKEN.items():
            if src.get(role):
                tok[token] = src[role]
        term = src.get("terminal") or {}
        for key, token in TERMINAL_TOKENS.items():
            if term.get(key):
                tok[token] = term[key]
        for side in ("normal", "bright"):
            for color, hexv in (term.get(side) or {}).items():
                tok[f"terminal_{side}_{color}"] = hexv
        surface = tok.get("surface")
        variant = tok.get("surface_variant") or surface
        if surface and variant:
            for name, level in CONTAINER_LEVELS.items():
                tok[name] = _mix_rgb(surface, variant, level)
        for alias, target in ALIASES.items():
            if tok.get(target):
                tok[alias] = tok[target]
        out[mode] = tok
    return out


GTK3_TEMPLATE = """\
/*
 * shadcn-theme-forge GTK3 template — tweakcn/shadcn vocabulary, native engine.
 * Generated roles come straight from the community palette's exact hexes.
 */

@define-color accent_color {{ colors.primary.default.hex }};
@define-color accent_bg_color {{ colors.primary.default.hex }};
@define-color accent_fg_color {{ colors.on_primary.default.hex }};

@define-color destructive_bg_color {{ colors.error.default.hex }};
@define-color destructive_fg_color {{ colors.on_error.default.hex }};
@define-color error_bg_color {{ colors.error.default.hex }};
@define-color error_fg_color {{ colors.on_error.default.hex }};

@define-color window_bg_color {{ colors.background.default.hex }};
@define-color window_fg_color {{ colors.on_background.default.hex }};

@define-color view_bg_color {{ colors.surface.default.hex }};
@define-color view_fg_color {{ colors.on_surface.default.hex }};

@define-color headerbar_bg_color {{ colors.surface_container.default.hex }};
@define-color headerbar_fg_color {{ colors.on_surface.default.hex }};
@define-color headerbar_backdrop_color @window_bg_color;

@define-color popover_bg_color {{ colors.surface_container_high.default.hex }};
@define-color popover_fg_color {{ colors.on_surface.default.hex }};

@define-color card_bg_color {{ colors.surface_container.default.hex }};
@define-color card_fg_color {{ colors.on_surface.default.hex }};

@define-color dialog_bg_color {{ colors.surface.default.hex }};
@define-color dialog_fg_color {{ colors.on_surface.default.hex }};

@define-color overview_bg_color {{ colors.surface_container.default.hex }};
@define-color overview_fg_color {{ colors.on_surface.default.hex }};

@define-color sidebar_bg_color {{ colors.surface_container_low.default.hex }};
@define-color sidebar_fg_color {{ colors.on_surface_variant.default.hex }};

@define-color backdrop_bg_color {{ colors.scrim.default.hex | set_alpha 0.6 }};

@define-color text_color {{ colors.on_surface.default.hex }};
@define-color insensitive_bg_color {{ colors.surface_variant.default.hex }};
@define-color insensitive_fg_color {{ colors.on_surface_variant.default.hex }};

@define-color fg_color {{ colors.on_surface.default.hex }};
@define-color bg_color {{ colors.surface.default.hex }};

/* Shared shadcn component grammar.  These rules intentionally use GTK's
 * stable widget nodes/classes so GTK3 and GTK4 applications inherit the same
 * shape, density, borders, and interaction hierarchy as the native shell. */
@define-color shadcn_border {{ colors.outline_variant.default.hex }};
@define-color shadcn_focus {{ colors.primary.default.hex }};
@define-color shadcn_control {{ colors.surface_container.default.hex }};
@define-color shadcn_control_hover {{ colors.surface_container_high.default.hex }};
@define-color shadcn_selection {{ colors.primary.default.hex }};
@define-color shadcn_selection_fg {{ colors.on_primary.default.hex }};

window,
dialog,
.background {
  background-color: @window_bg_color;
  color: @window_fg_color;
}

headerbar {
  min-height: 40px;
  padding: 4px 8px;
  background-image: none;
  background-color: @headerbar_bg_color;
  border-bottom: 1px solid @shadcn_border;
  box-shadow: none;
}

button,
entry,
spinbutton,
combobox > box {
  min-height: 32px;
  border: 1px solid @shadcn_border;
  border-radius: 8px;
  box-shadow: none;
}

button {
  padding: 4px 12px;
  background-image: none;
  background-color: @shadcn_control;
  color: @window_fg_color;
}

/* Toolbars must remain usable in split-screen and laptop-width windows. Keep
 * the 40px desktop control rhythm for forms, but use compact icon geometry in
 * header bars so Nautilus can preserve its path and primary actions. */
headerbar button {
  min-width: 32px;
  min-height: 32px;
  padding: 2px 6px;
}

headerbar button.image-button,
headerbar button.circular {
  padding: 2px;
}

/* Window chrome should read as glyphs, not another toolbar button group. Keep
 * a compact hit target and reveal a surface only during pointer interaction. */
headerbar windowcontrols button {
  min-width: 28px;
  min-height: 28px;
  padding: 2px;
  background-color: transparent;
  border-color: transparent;
  box-shadow: none;
}

headerbar windowcontrols button:hover {
  background-color: @shadcn_control_hover;
  border-color: transparent;
}

headerbar windowcontrols button:active {
  background-color: @shadcn_selection;
  color: @shadcn_selection_fg;
}

headerbar entry,
headerbar combobox > box {
  min-height: 32px;
  padding: 2px 8px;
}

button:hover,
row:hover {
  background-color: @shadcn_control_hover;
}

button:active,
button:checked,
row:selected {
  background-color: @shadcn_selection;
  color: @shadcn_selection_fg;
}

button.suggested-action {
  background-color: @accent_bg_color;
  color: @accent_fg_color;
  border-color: @accent_bg_color;
}

button.destructive-action {
  background-color: @destructive_bg_color;
  color: @destructive_fg_color;
  border-color: @destructive_bg_color;
}

entry,
spinbutton,
combobox > box {
  padding: 4px 10px;
  background-color: @view_bg_color;
  color: @view_fg_color;
}

button:focus,
entry:focus,
spinbutton:focus,
combobox:focus > box {
  border-color: @shadcn_focus;
  box-shadow: 0 0 0 2px alpha(@shadcn_focus, 0.28);
}

popover > contents,
menu,
.menu,
.card {
  background-color: @popover_bg_color;
  color: @popover_fg_color;
  border: 1px solid @shadcn_border;
  border-radius: 12px;
  box-shadow: 0 8px 24px alpha(black, 0.24);
}

/* GtkPopoverMenu already provides its own menu surface. Keeping the generic
 * popover surface beneath it creates a second padded box around Nautilus's
 * hamburger menu, so make only that redundant outer node transparent. */
popover.menu > contents {
  padding: 0;
  background-color: transparent;
  border: none;
  box-shadow: none;
}

list,
listview,
columnview,
gridview {
  background-color: @view_bg_color;
  color: @view_fg_color;
}

row {
  min-height: 36px;
  border-radius: 8px;
}

separator {
  background-color: @shadcn_border;
  min-width: 1px;
  min-height: 1px;
}
"""

GTK4_TEMPLATE = GTK3_TEMPLATE.replace("GTK3", "GTK4") + """\

/* libadwaita 1.8+ consumes CSS custom properties in addition to the legacy
 * symbolic colors above.  Keep both maps so Nautilus and classic GTK4 apps
 * resolve the same semantic source. */
:root {
  --accent-color: {{ colors.primary.default.hex }};
  --accent-bg-color: {{ colors.primary.default.hex }};
  --accent-fg-color: {{ colors.on_primary.default.hex }};
  --destructive-bg-color: {{ colors.error.default.hex }};
  --destructive-fg-color: {{ colors.on_error.default.hex }};
  --error-color: {{ colors.error.default.hex }};
  --error-bg-color: {{ colors.error.default.hex }};
  --error-fg-color: {{ colors.on_error.default.hex }};
  --window-bg-color: {{ colors.background.default.hex }};
  --window-fg-color: {{ colors.on_background.default.hex }};
  --view-bg-color: {{ colors.surface.default.hex }};
  --view-fg-color: {{ colors.on_surface.default.hex }};
  --headerbar-bg-color: {{ colors.surface_container.default.hex }};
  --headerbar-fg-color: {{ colors.on_surface.default.hex }};
  --popover-bg-color: {{ colors.surface_container_high.default.hex }};
  --popover-fg-color: {{ colors.on_surface.default.hex }};
  --card-bg-color: {{ colors.surface_container.default.hex }};
  --card-fg-color: {{ colors.on_surface.default.hex }};
  --dialog-bg-color: {{ colors.surface.default.hex }};
  --dialog-fg-color: {{ colors.on_surface.default.hex }};
  --sidebar-bg-color: {{ colors.surface_container_low.default.hex }};
  --sidebar-fg-color: {{ colors.on_surface_variant.default.hex }};
  --sidebar-border-color: {{ colors.outline_variant.default.hex }};
  --warning-color: {{ colors.tertiary.default.hex }};
  --warning-bg-color: {{ colors.tertiary.default.hex }};
  --warning-fg-color: {{ colors.on_tertiary.default.hex }};
  --success-color: {{ colors.secondary.default.hex }};
  --success-bg-color: {{ colors.secondary.default.hex }};
  --success-fg-color: {{ colors.on_secondary.default.hex }};
  --shade-color: alpha({{ colors.scrim.default.hex }}, 0.36);
}

/* Nautilus lays out its sidebar and content as sibling panes. Give both
 * headerbars the same 60 px outer height so their lower dividers share one
 * structural baseline. GTK includes the padding in this minimum allocation. */
.sidebar-pane headerbar,
.content-pane headerbar {
  min-height: 60px;
  padding-top: 4px;
  padding-bottom: 4px;
}

/* The sidebar toolbar positions its headerbar 3 px above the content toolbar.
 * Shift that headerbar within its existing allocation so both panes use the
 * same native border rendering on the same baseline. */
.sidebar-pane headerbar {
  margin-top: 3px;
  margin-bottom: -3px;
}

/* Keep every navigation row at its native height. Continue the content-header
 * baseline through the standard gap before the second row. */
.navigation-sidebar > row:nth-child(2) {
  margin-top: 3px;
  border-top: 1px solid @shadcn_border;
}

/* Sidebar selection is a flat navigation state, not a raised primary button. */
.navigation-sidebar > row:selected {
  background-color: @shadcn_selection;
  color: @shadcn_selection_fg;
  border: none;
  box-shadow: none;
}

/* Trash exposes an AdwBanner with no title and one trailing action. Remove the
 * oversized panel treatment so the action remains compact and the surrounding
 * space reads as part of the file view. */
.content-pane banner > revealer > widget {
  margin-top: 0;
  margin-bottom: 0;
  background-color: @view_bg_color;
  border: none;
  box-shadow: none;
}

/* A column header is one table control, not a row of floating cards. Preserve
 * column affordances with subtle internal separators and rounded outer ends. */
.nautilus-list-view columnview > header > button {
  margin: 0;
  border-radius: 0;
  border-left-width: 0;
  border-right-width: 1px;
  background-color: @shadcn_control;
  box-shadow: none;
}

.nautilus-list-view columnview > header > button:first-child {
  border-radius: 8px 0 0 8px;
}

.nautilus-list-view columnview > header > button:last-child {
  border-right-width: 0;
  border-radius: 0 8px 8px 0;
}

/* Nautilus adds a list-view gutter by default. Let the table and its unified
 * column header use the full content width; cell padding preserves row rhythm. */
.nautilus-list-view columnview {
  padding-left: 0;
  padding-right: 0;
}
"""

# shadcn-flavored kitty config: palette from our flattened terminal tokens
# (forge derives ANSI colors from the preset's chart tokens).
KITTY_TEMPLATE = """\
# shadcn-theme-forge kitty theme (generated by Noctalia's template engine)
foreground {{ colors.terminal_foreground.default.hex }}
background {{ colors.terminal_background.default.hex }}
cursor {{ colors.terminal_cursor.default.hex }}
cursor_text_color {{ colors.terminal_cursor_text.default.hex }}
selection_foreground {{ colors.terminal_selection_fg.default.hex }}
selection_background {{ colors.terminal_selection_bg.default.hex }}
active_border_color {{ colors.primary.default.hex }}
inactive_border_color {{ colors.surface_variant.default.hex }}

color0  {{ colors.on_surface_variant.default.hex }}
color1  {{ colors.terminal_normal_red.default.hex }}
color2  {{ colors.terminal_normal_green.default.hex }}
color3  {{ colors.terminal_normal_yellow.default.hex }}
color4  {{ colors.terminal_normal_blue.default.hex }}
color5  {{ colors.terminal_normal_magenta.default.hex }}
color6  {{ colors.terminal_normal_cyan.default.hex }}
color7  {{ colors.terminal_normal_white.default.hex }}
color8  {{ colors.on_surface_variant.default.hex }}
color9  {{ colors.terminal_bright_red.default.hex }}
color10 {{ colors.terminal_bright_green.default.hex }}
color11 {{ colors.terminal_bright_yellow.default.hex }}
color12 {{ colors.terminal_bright_blue.default.hex }}
color13 {{ colors.terminal_bright_magenta.default.hex }}
color14 {{ colors.terminal_bright_cyan.default.hex }}
color15 {{ colors.terminal_bright_white.default.hex }}
"""

# Terminal emulators: all hex values are quoted because '#' starts a comment
# in INI/TOML and noctalia hexes begin with '#'. set_alpha is deliberately
# unused in foot/alacritty/wezterm — their palettes must stay opaque.
FOOT_TEMPLATE = """\
# shadcn-theme-forge foot theme (generated by Noctalia's template engine)
[colors]
background = "{{ colors.terminal_background.default.hex }}"
foreground = "{{ colors.terminal_foreground.default.hex }}"
alpha = 1.0

[cursor]
style = block
color = "{{ colors.terminal_cursor.default.hex }} {{ colors.terminal_cursor_text.default.hex }}"

[selection]
foreground = "{{ colors.terminal_selection_fg.default.hex }}"
background = "{{ colors.terminal_selection_bg.default.hex }}"

[colors.normal]
black = "{{ colors.on_surface_variant.default.hex }}"
red = "{{ colors.terminal_normal_red.default.hex }}"
green = "{{ colors.terminal_normal_green.default.hex }}"
yellow = "{{ colors.terminal_normal_yellow.default.hex }}"
blue = "{{ colors.terminal_normal_blue.default.hex }}"
magenta = "{{ colors.terminal_normal_magenta.default.hex }}"
cyan = "{{ colors.terminal_normal_cyan.default.hex }}"
white = "{{ colors.terminal_normal_white.default.hex }}"

[colors.bright]
black = "{{ colors.on_surface_variant.default.hex }}"
red = "{{ colors.terminal_bright_red.default.hex }}"
green = "{{ colors.terminal_bright_green.default.hex }}"
yellow = "{{ colors.terminal_bright_yellow.default.hex }}"
blue = "{{ colors.terminal_bright_blue.default.hex }}"
magenta = "{{ colors.terminal_bright_magenta.default.hex }}"
cyan = "{{ colors.terminal_bright_cyan.default.hex }}"
white = "{{ colors.terminal_bright_white.default.hex }}"
"""

ALACRITTY_TEMPLATE = """\
# shadcn-theme-forge alacritty theme (generated by Noctalia's template engine)
[colors.primary]
background = "{{ colors.terminal_background.default.hex }}"
foreground = "{{ colors.terminal_foreground.default.hex }}"

[colors.cursor]
text = "{{ colors.terminal_cursor_text.default.hex }}"
cursor = "{{ colors.terminal_cursor.default.hex }}"

[colors.selection]
text = "{{ colors.terminal_selection_fg.default.hex }}"
background = "{{ colors.terminal_selection_bg.default.hex }}"

[colors.normal]
black = "{{ colors.on_surface_variant.default.hex }}"
red = "{{ colors.terminal_normal_red.default.hex }}"
green = "{{ colors.terminal_normal_green.default.hex }}"
yellow = "{{ colors.terminal_normal_yellow.default.hex }}"
blue = "{{ colors.terminal_normal_blue.default.hex }}"
magenta = "{{ colors.terminal_normal_magenta.default.hex }}"
cyan = "{{ colors.terminal_normal_cyan.default.hex }}"
white = "{{ colors.terminal_normal_white.default.hex }}"

[colors.bright]
black = "{{ colors.on_surface_variant.default.hex }}"
red = "{{ colors.terminal_bright_red.default.hex }}"
green = "{{ colors.terminal_bright_green.default.hex }}"
yellow = "{{ colors.terminal_bright_yellow.default.hex }}"
blue = "{{ colors.terminal_bright_blue.default.hex }}"
magenta = "{{ colors.terminal_bright_magenta.default.hex }}"
cyan = "{{ colors.terminal_bright_cyan.default.hex }}"
white = "{{ colors.terminal_bright_white.default.hex }}"
"""

# Flat table assignments only — no inline { } tables, so template braces and
# Lua table braces can never end up adjacent ({{ / }}) in the source.
WEZTERM_TEMPLATE = """\
-- shadcn-theme-forge wezterm theme (generated by Noctalia's template engine)
local ret = {}
ret.background = "{{ colors.terminal_background.default.hex }}"
ret.foreground = "{{ colors.terminal_foreground.default.hex }}"
ret.cursor_bg = "{{ colors.terminal_cursor.default.hex }}"
ret.cursor_fg = "{{ colors.terminal_cursor_text.default.hex }}"
ret.cursor_edge_color = "{{ colors.primary.default.hex }}"
ret.selection_background = "{{ colors.terminal_selection_bg.default.hex }}"
ret.selection_foreground = "{{ colors.terminal_selection_fg.default.hex }}"

ret.ansi = {
  "{{ colors.on_surface_variant.default.hex }}",
  "{{ colors.terminal_normal_red.default.hex }}",
  "{{ colors.terminal_normal_green.default.hex }}",
  "{{ colors.terminal_normal_yellow.default.hex }}",
  "{{ colors.terminal_normal_blue.default.hex }}",
  "{{ colors.terminal_normal_magenta.default.hex }}",
  "{{ colors.terminal_normal_cyan.default.hex }}",
  "{{ colors.terminal_normal_white.default.hex }}",
}

ret.brights = {
  "{{ colors.on_surface_variant.default.hex }}",
  "{{ colors.terminal_bright_red.default.hex }}",
  "{{ colors.terminal_bright_green.default.hex }}",
  "{{ colors.terminal_bright_yellow.default.hex }}",
  "{{ colors.terminal_bright_blue.default.hex }}",
  "{{ colors.terminal_bright_magenta.default.hex }}",
  "{{ colors.terminal_bright_cyan.default.hex }}",
  "{{ colors.terminal_bright_white.default.hex }}",
}

return ret
"""

# Waybar loads its stylesheet standalone, so we emit direct hexes instead of
# @define-color/@name references (those only resolve if gtk.css is loaded in
# the same GTK context — fragile coupling; waybar's CSS parser varies too).
WAYBAR_TEMPLATE = """\
/*
 * shadcn-theme-forge waybar theme (generated by Noctalia's template engine).
 * Direct hex values only: waybar loads this file alone, no @define-color
 * coupling to gtk.css.
 */

* {
  background: {{ colors.surface_container.default.hex }};
  color: {{ colors.on_surface.default.hex }};
  border-color: {{ colors.outline.default.hex }};
}

#workspaces button {
  color: {{ colors.on_surface_variant.default.hex }};
}

#workspaces button:hover {
  background: {{ colors.hover.default.hex | set_alpha 0.4 }};
  color: {{ colors.on_hover.default.hex }};
}

#workspaces button.active {
  background: {{ colors.primary.default.hex }};
  color: {{ colors.on_primary.default.hex }};
}

#workspaces button.urgent {
  background: {{ colors.error.default.hex }};
  color: {{ colors.on_error.default.hex }};
}

#window {
  color: {{ colors.on_surface.default.hex }};
}

#clock {
  color: {{ colors.on_surface_variant.default.hex }};
}

#tray > .passive {
  color: {{ colors.on_surface_variant.default.hex }};
}

#idle_inhibit.activated,
#battery.warning {
  color: {{ colors.tertiary.default.hex }};
}

#battery.critical {
  color: {{ colors.error.default.hex }};
}

#mode {
  background: {{ colors.primary.default.hex }};
  color: {{ colors.on_primary.default.hex }};
}
"""

# Manifest mirrors noctalia-dev/community-templates layout, in user-template
# form. NOTE (docs): for *user* templates {{ config_dir }} resolves to
# ~/.config/noctalia, not this templates dir — hooks must use full paths.
# No hooks are shipped yet, so nothing reaches anywhere.
TEMPLATES_TOML_HEADER = """\
# shadcn-theme-forge user templates — install by copying these sections into
# ~/.config/noctalia/config.toml (paths must be absolute for user templates):
#
#   [theme.templates.user.shadcn_gtk3]
#   input_path  = "~/shadcn-theme-forge/out/templates/gtk3.css"
#   output_path = "$XDG_CONFIG_HOME/gtk-3.0/noctalia.css"
#
# (same shape for shadcn_gtk4, shadcn_kitty, shadcn_foot, shadcn_alacritty,
#  shadcn_wezterm, shadcn_waybar — adjust input/output paths accordingly)
#
# Then: noctalia theme --list-templates  (confirms pickup)
# Live apply: noctalia msg templates-apply
"""


class AdapterDescriptor(NamedTuple):
    """Canonical native-adapter metadata shared by every generation surface."""

    name: str
    filename: str
    output_path: str
    template: str
    sentinel: str
    color_token: str


ADAPTERS: tuple[AdapterDescriptor, ...] = (
    AdapterDescriptor("shadcn_gtk3", "gtk3.css", "$XDG_CONFIG_HOME/gtk-3.0/noctalia.css", GTK3_TEMPLATE, "@define-color accent_color", "primary"),
    AdapterDescriptor("shadcn_gtk4", "gtk4.css", "$XDG_CONFIG_HOME/gtk-4.0/noctalia.css", GTK4_TEMPLATE, "@define-color accent_color", "primary"),
    AdapterDescriptor("shadcn_kitty", "kitty.conf", "$XDG_CONFIG_HOME/kitty/themes/shadcn.conf", KITTY_TEMPLATE, "background ", "terminal_background"),
    AdapterDescriptor("shadcn_foot", "foot.ini", "$XDG_CONFIG_HOME/foot/noctalia.ini", FOOT_TEMPLATE, "[colors]", "terminal_background"),
    AdapterDescriptor("shadcn_alacritty", "alacritty.toml", "$XDG_CONFIG_HOME/alacritty/noctalia.toml", ALACRITTY_TEMPLATE, "[colors.primary]", "terminal_background"),
    AdapterDescriptor("shadcn_wezterm", "wezterm.lua", "$XDG_CONFIG_HOME/wezterm/noctalia.lua", WEZTERM_TEMPLATE, "local ret = {}", "terminal_background"),
    AdapterDescriptor("shadcn_waybar", "waybar.css", "$XDG_CONFIG_HOME/waybar/noctalia.css", WAYBAR_TEMPLATE, "#workspaces button.active", "primary"),
)


def templates_manifest() -> str:
    sections = [TEMPLATES_TOML_HEADER.rstrip(), ""]
    for adapter in ADAPTERS:
        sections.extend(
            (
                f"[templates.{adapter.name}]",
                f'input_path  = "$XDG_CONFIG_HOME/noctalia/templates/shadcn/{adapter.filename}"',
                f'output_path = "{adapter.output_path}"',
                "",
            )
        )
    return "\n".join(sections)


def write_previews(pals: dict[str, dict]) -> int:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for name, pal in pals.items():
        (PREVIEW_DIR / f"{name}.json").write_text(json.dumps(theme_json(pal), indent=2))
    return len(pals)


def write_templates() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for adapter in ADAPTERS:
        (TEMPLATES_DIR / adapter.filename).write_text(adapter.template)
    (TEMPLATES_DIR / "templates.toml").write_text(templates_manifest())


def verify(
    preview_name: str,
    tmpl: Path = TEMPLATES_DIR / "gtk3.css",
    *,
    mode: str = "dark",
    output_suffix: str | None = None,
    sentinel: str | None = None,
    expected_color: str | None = None,
) -> bool:
    """Offline render: preview map + template through the real engine.

    Works for any output format (css/ini/toml/lua) — the engine substitutes
    text; we only assert the file rendered and no {{ }} placeholders remain.
    """
    if mode not in {"light", "dark"}:
        raise ValueError(f"invalid render mode: {mode}")
    if not tmpl.is_file():
        raise ValueError(f"template does not exist: {tmpl}")
    src = PREVIEW_DIR / f"{preview_name}.json"
    if not src.is_file():
        raise ValueError(f"preview does not exist: {src}")
    with tempfile.TemporaryDirectory() as td:
        suffix = output_suffix or tmpl.suffix or ".out"
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        out = Path(td) / f"rendered{suffix}"
        proc = subprocess.run(
            ["noctalia", "theme", "--theme-json", str(src),
             "--default-mode", mode, "-r", f"{tmpl}:{out}"],
            capture_output=True, text=True, timeout=30,
        )
        diagnostic = proc.stderr[-2000:].strip()
        label = f"{preview_name}/{mode}/{tmpl.name}"
        if proc.returncode != 0:
            print(f"VERIFY FAIL ({label}): Noctalia exited {proc.returncode}: {diagnostic}")
            return False
        if not out.is_file() or out.stat().st_size == 0:
            print(f"VERIFY FAIL ({label}): engine wrote no nonempty output: {diagnostic}")
            return False
        rendered = out.read_text()
        bad = [ln for ln in rendered.splitlines() if "{{" in ln or "}}" in ln]
        if bad:
            print(f"VERIFY FAIL ({label}): unresolved placeholders:\n" + "\n".join(bad[:20]))
            return False
        if sentinel and sentinel not in rendered:
            print(f"VERIFY FAIL ({label}): missing format sentinel {sentinel!r}")
            return False
        if expected_color and expected_color.lower() not in rendered.lower():
            print(f"VERIFY FAIL ({label}): missing mode color {expected_color}")
            return False
        lines = [ln for ln in rendered.splitlines() if ln.strip()]
        print(f"VERIFY OK ({label}): {len(lines)} lines")
        return True


def verify_native_matrix() -> bool:
    """Qualify every adapter with neutral light and dark-first dark themes."""
    representatives = (("graphite", "light"), ("cosmic-night", "dark"))
    ok = True
    for preview_name, mode in representatives:
        payload = json.loads((PREVIEW_DIR / f"{preview_name}.json").read_text())
        tokens = payload.get(mode, {})
        for adapter in ADAPTERS:
            expected_color = tokens.get(adapter.color_token)
            if not expected_color:
                print(f"VERIFY FAIL ({preview_name}/{mode}/{adapter.filename}): missing token {adapter.color_token}")
                ok = False
                continue
            ok = verify(
                preview_name,
                TEMPLATES_DIR / adapter.filename,
                mode=mode,
                output_suffix=Path(adapter.filename).suffix,
                sentinel=adapter.sentinel,
                expected_color=expected_color,
            ) and ok
    return ok


def main() -> int:
    reg = load_registry()
    pals = {item["name"]: noctalia_palette(item) for item in reg.get("items", [])}
    write_templates()
    n = write_previews(pals)
    print(f"previews: {n} presets -> {PREVIEW_DIR}")
    print(f"templates: {len(ADAPTERS)} adapters + manifest -> {TEMPLATES_DIR}")
    ok = verify_native_matrix()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

# CLAUDE.md

Guidance for agents working in this repository.

## Product contract

This repository turns the 36 cached tweakcn/shadcn presets in `registry.json`
into two related products:

- an offline shadcn-style component and state gallery for full-retheme asset
  work; and
- Noctalia palettes and seven native adapter templates: GTK 3, GTK 4, Kitty,
  Foot, Alacritty, WezTerm, and Waybar.

`DESIGN.md` is the active design contract. Preserve its central boundary: the
fixed graphite gallery shell must not influence specimen styling. Specimens use
the selected preset's semantic CSS variables, without per-preset branches or
hard-coded corrections. `mapping.md` documents the separate shadcn-to-Noctalia
translation used by native outputs.

`docs/research-theme-gallery-conventions.md` records the design research behind
the gallery. Where it suggests injecting Google Fonts, the active offline
contract takes precedence: the implementation uses local font fallbacks and
loads no remote fonts.

The implementation is Python-standard-library-only. The generated gallery is a
single self-contained HTML file with no framework, build step, server, remote
asset, or network request.

## Commands

```bash
# Generate and structurally verify the offline gallery.
python3 gallery.py

# Verify the existing gallery without rewriting it.
python3 gallery.py --verify

# Run the regression suite.
python3 -m unittest discover -s tests -v

# Generate CSS, the manifest, and palettes in a repository-local sandbox.
python3 forge.py --noctalia-dir out/palettes-test

# Inspect generation without creating or changing any files.
python3 forge.py --dry-run

# Generate preview token maps and all seven native templates.
python3 templates.py
```

Open `out/gallery/index.html` directly in a browser after running
`python3 gallery.py`. It works from `file://`; no local server is required.

`templates.py` uses the external `noctalia` CLI to smoke-test all seven
templates against Graphite after generation. Gallery generation, forge
generation, and the unit tests do not require third-party Python packages.

## Architecture

```text
registry.json (36 cached tweakcn presets)
  |-- gallery.py
  |     `-- out/gallery/index.html
  |
  `-- forge.py
        |-- out/css/tweakcn/<name>.css
        |-- out/index.json
        `-- <palette-dir>/<name>.json
              `-- templates.py
                    |-- out/preview/<name>.json
                    `-- out/templates/*
```

- `gallery.py` embeds the registry metadata and light/dark variables into one
  document. It covers Overview, Actions, Forms, Overlays, Data, Navigation,
  Feedback, and Tokens. Its verifier checks preset parity, offline safety,
  unresolved placeholders, token ownership, and required sections.
- `forge.py` converts CSS colors to Noctalia's opaque role and terminal palette
  format while preserving the original CSS variables for web consumers.
- `oklch.py` is the stdlib OKLCH-to-sRGB conversion layer. Unsupported color
  formats return `None`; the forge emits a warning when a shadow color needs its
  documented background fallback.
- `templates.py` expands Noctalia roles into snake_case template tokens and
  writes GTK, terminal, and Waybar adapters.

## Output layout

```text
out/gallery/index.html                 self-contained gallery
out/css/tweakcn/<name>.css             original light/dark shadcn variables
out/index.json                         36-preset catalog
out/palettes-test/<name>.json          safe local palette target
out/preview/<name>.json                Noctalia template token maps
out/templates/gtk3.css                 GTK 3 adapter
out/templates/gtk4.css                 GTK 4 adapter
out/templates/kitty.conf               Kitty adapter
out/templates/foot.ini                 Foot adapter
out/templates/alacritty.toml           Alacritty adapter
out/templates/wezterm.lua              WezTerm adapter
out/templates/waybar.css               Waybar adapter
out/templates/templates.toml           adapter installation manifest
```

Without `--noctalia-dir`, `forge.py` writes palettes to
`~/.config/noctalia/palettes/`. Prefer `out/palettes-test` during development.
`--dry-run` is strictly read-only: it does not create a registry cache, output
directories, palettes, CSS, or a replacement manifest.

## Verification boundary

The automated gallery verifier proves document structure and token/offline
invariants; it does not prove visual appearance in a real browser. There is no
canonical screenshot or visual-regression baseline yet. Treat browser review
across representative presets, both modes, responsive widths, and keyboard
states as a separate validation pass before approving visual changes.

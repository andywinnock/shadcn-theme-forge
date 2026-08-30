# shadcn Theme Forge

A zero-dependency Python pipeline for inspecting and translating 36
tweakcn/shadcn themes. It generates a self-contained component gallery for UI
asset work plus Noctalia palettes and native templates for GTK 3, GTK 4, Kitty,
Foot, Alacritty, WezTerm, and Waybar.

> [!WARNING]
> This is an experimental Linux desktop integration. Start with repository-local
> generation and a dry-run plan. Live installation changes user configuration;
> use the documented transactional apply, verify, and rollback commands.

## Project status

The native integration currently targets Noctalia v5 on Niri, GTK 3/4 and
libadwaita applications, Qt/Kvantum applications, and common terminal
emulators. It is a community project, not an official shadcn, tweakcn,
Noctalia, KDE, GNOME, or Kitty project. See `DESIGN.md` for the component
contract, `mapping.md` for semantic token decisions, and `CONTRIBUTING.md` for
development and bug-reporting guidance.

## Start the gallery

```bash
python3 gallery.py
```

Then open `out/gallery/index.html` directly in a browser. The generated page is
self-contained and works from `file://`: it needs no npm install, build step,
local server, remote asset, or network connection.

Use the preset selector and light/dark control to inspect all 36 themes across
Overview, Actions, Forms, Overlays, Data, Navigation, Feedback, and Tokens. The
gallery includes component variants and persistent interaction-state examples
for full-retheme asset review.

## Verify

```bash
python3 verify_release.py
```

The release runner is fail-closed. It performs deterministic generation twice,
all unit tests, required Pyright checking, gallery static verification, Chromium
browser QA, the fourteen-render native matrix, shell-pack verification, and
offline Noctalia configuration validation. Its normalized summaries are written
to ignored `out/qa/release-summary.json` and `out/qa/release-summary.md`; no live
XDG configuration is read, written, or activated.

Chromium on Linux is the automated reference browser. Reviewed visual baselines
live under `tests/baselines/chromium-linux-<major>/`; transient captures and
isolated browser profiles live under ignored `out/qa/`. Firefox local-file smoke
is informational when available. Safari remains an explicitly unverified macOS
portability gap and is not represented as automated release evidence.

For a narrower development loop, run:

```bash
python3 gallery.py --verify
python3 -m unittest discover -s tests -q
pyright forge.py gallery.py oklch.py templates.py shell_pack.py browser_qa.py verify_release.py tests
```

## Generate theme outputs

Use a repository-local palette directory while developing:

```bash
python3 forge.py --noctalia-dir out/palettes-test
python3 templates.py
```

`forge.py` emits preserved shadcn CSS, a catalog, and Noctalia palettes.
`templates.py` emits preview token maps and all seven native adapters from one
canonical descriptor, then uses the external `noctalia` CLI for a blocking
matrix: Graphite light and Cosmic Night dark across every adapter (14 real
renders). Each render requires a zero engine exit, a nonempty output, no
unresolved placeholders, a format sentinel, and the expected mode-derived
color. The project runtime uses only the Python standard library; `noctalia` and
Pyright are release-verification tools.

## Native component unification

Two component-level integrations extend the seven palette adapters:

- `native/noctalia/build_native.sh` builds the pinned Noctalia profile into
  `out/native/noctalia-root`, runs the upstream suite, and never replaces
  `/usr/bin/noctalia`. `native/noctalia/run_native.sh` preserves the packaged
  binary as a validated fallback.
- `native/qt/manage.py` generates Graphite light/dark Kvantum, qt5ct, qt6ct,
  and KDE color-scheme assets. Its default is plan-only. `--apply` records a
  byte-exact rollback journal; `--verify` and `--rollback` fail closed when a
  managed file has changed.

```bash
native/noctalia/build_native.sh
python3 native/qt/manage.py --mode dark
python3 native/qt/manage.py --mode dark --apply
python3 native/qt/manage.py --verify
```

The shared component contract uses 40px controls, 8px control radii, 12px card
radii, 16px floating shell surfaces, one-pixel semantic outlines, and palette-
owned interaction states. GTK/libadwaita, Qt/Kvantum, terminals, and the native
shell consume the same semantic source without patching system files.

To inspect a run without writing any files:

```bash
python3 forge.py --dry-run
```

Dry-run mode does not create or modify the registry cache, output directories,
palettes, CSS, or manifest.

## Build the Noctalia v5 shell pack

`shell_pack.py` owns the reproducible shell replacement layer. Its default is a
repository-local render; it never forks Noctalia, replaces `/usr/bin` files, or
modifies live configuration:

```bash
python3 shell_pack.py
python3 shell_pack.py verify
```

The inspectable pack is written to `out/shell-pack/` and contains all 36 custom
palettes, all seven adapter templates, deterministic Graphite sample outputs,
and a sanitized v5 configuration bundle for the bar, dock, widgets, theme, and
user templates. The bundle contains no credentials, monitor identifiers,
absolute home paths, or host-specific pinned applications.

The shell pack supplies palettes, adapter templates, and theme configuration.
It deliberately does not add bars, docks, or desktop-widget instances to an
existing profile, preventing duplicate shell surfaces. The
repo-owned native Noctalia build in `native/noctalia/` applies the shared
component grammar to the compiled shell controls and compositions; the pack
does not patch or replace the packaged `/usr/bin/noctalia` binary.

Plan an XDG-aware installation without changing user files:

```bash
python3 shell_pack.py plan
```

Live installation requires both the `apply` command and the explicit `--apply`
flag. Existing files are compared first, unchanged files are skipped, and a
durable pre-mutation journal plus timestamped backup make the file operation
transactional. A failed write is reversed automatically. Existing file modes
are preserved, and the forge uses its own root-level TOML file so unrelated
Noctalia config remains intact. Adapter outputs remain owned by Noctalia's
separate `templates-apply` activation step, so the installer never writes
through application config symlinks. Live mutations, backups, and rollback use
descriptor-relative Linux filesystem operations with `O_NOFOLLOW`; validated
parent directories stay pinned through replacement so path swaps cannot
redirect writes:

```bash
python3 shell_pack.py apply --apply
python3 shell_pack.py verify --installed
```

Live Noctalia state is a separate, explicit operation after the installed files
verify. `activate` refuses sandbox or alternate `--config-dir` values, requiring
the currently resolved active Noctalia profile, then confirms its managed config
and selected palette are installed and parse correctly. It uses argv-only subprocesses and an
allowlist limited to `config validate`, `config-reload`, `color-scheme-set
custom`, and `templates-apply`:

```bash
python3 shell_pack.py activate --apply --activate graphite
```

Rollback is explicit and restores the newest backup by default. A specific
backup directory may be passed with `--backup`. Rollback is bound to the
verified pack manifest and managed target set, verifies installed hashes and
modes first, and refuses the entire rollback if any file was edited after apply:

```bash
python3 shell_pack.py rollback
```

The installer refuses symlink targets or ancestors, non-file targets, relative
XDG roots, and an existing `90-shadcn-theme-forge.toml` that lacks its ownership
marker. Override the destination for sandbox tests with an absolute
`--config-dir`; normal resolution honors `NOCTALIA_CONFIG_HOME`, then
`XDG_CONFIG_HOME`, then `~/.config`. Render atomically replaces the generated
pack, while verify rejects stale or unmanifested pack files.

## How it fits together

```text
registry.json
  |-- gallery.py --> out/gallery/index.html
  `-- forge.py   --> out/css/tweakcn/*.css
                  + out/index.json
                  + Noctalia palettes
                        `-- templates.py --> out/preview/*.json
                                         + out/templates/*
```

The gallery preserves the source shadcn variables—including light/dark modes,
typography, radius, spacing, shadows, charts, and sidebar roles—for web
specimens. The native path converts those same sources to opaque Noctalia roles
and terminal colors. See `DESIGN.md` for the UI contract,
`docs/research-theme-gallery-conventions.md` for the research evidence, and
`mapping.md` for native semantic mapping decisions. The research note's Google
Fonts option is intentionally not implemented because the product must remain
offline; local font fallbacks are used instead.

## Outputs

| Path | Contents |
| --- | --- |
| `out/gallery/index.html` | Offline theme and component specimen gallery |
| `out/css/tweakcn/<name>.css` | Preserved shadcn CSS variables |
| `out/index.json` | Generated 36-preset catalog |
| `out/preview/<name>.json` | Expanded Noctalia template tokens |
| `out/templates/` | GTK 3/4, Kitty, Foot, Alacritty, WezTerm, and Waybar templates |
| `out/palettes-test/` | Safe repository-local Noctalia palettes |
| `out/shell-pack/` | Reproducible Noctalia v5 shell pack, manifest, and sample outputs |

By default, `forge.py` writes palettes to
`~/.config/noctalia/palettes/`. Pass `--noctalia-dir out/palettes-test` to keep
development output inside the repository.

## License

MIT. See `LICENSE`. Upstream projects and any derived theme assets retain their
own names, licenses, and attribution requirements.

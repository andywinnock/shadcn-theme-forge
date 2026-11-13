# Research: how themes are previewed & applied across the ecosystem

Compiled 2026-08-28 via web research (surfside search), to inform two planned
features: a static shadcn widget gallery (`gallery.py`) and noctalia template
adapters (foot/alacritty/wezterm/waybar). Sources listed at the bottom.

## 1. shadcn/ui theming is a CSS-variable contract (official docs)

Source: <https://ui.shadcn.com/docs/theming> (v4, oklch-era)

- Theming mechanism: CSS variables under `:root` (light) and `.dark` (dark).
  Components reference tokens via Tailwind utilities (`bg-background`,
  `text-primary-foreground`, `border-border`, `ring-ring`), so **redefining the
  variables themes everything without touching component code**.
- **Semantic pair convention**: every surface token `X` pairs with
  `X-foreground`, which controls *text and icons sitting on that surface*.
  The `-background` suffix is omitted for the surface token (`primary` sits
  under `primary-foreground`).
- **Official token → component map** (the "Used by" column — authoritative for
  a fidelity-focused gallery):

| Token pair | Controls | Used by |
|---|---|---|
| `background` / `foreground` | app shell | page shell, sections, default text |
| `card` / `card-foreground` | elevated surfaces | Card, dashboard/settings panels |
| `popover` / `popover-foreground` | floating surfaces | Popover, DropdownMenu, ContextMenu, overlays |
| `primary` / `primary-foreground` | high-emphasis, brand | default Button, selected states, badges, active accents |
| `secondary` / `secondary-foreground` | low-emphasis filled | secondary buttons, secondary badges |
| `muted` / `muted-foreground` | subtle surfaces | descriptions, placeholders, empty states, helper text |
| `accent` / `accent-foreground` | interactive hover/focus/active | ghost buttons, menu highlight, hovered rows, selected items |
| `destructive` | destructive actions/error | destructive buttons, invalid states |
| `border` | default borders | cards, menus, tables, separators |
| `input` | form-control borders | Input, Textarea, Select, outline buttons |
| `ring` | focus rings | all focusable controls |
| `chart-1..5` | chart palette | charts |
| `sidebar-*` | sidebar-specific roles | sidebar container, active item (`sidebar-primary`), hover (`sidebar-accent`), `sidebar-border`, `sidebar-ring` |
| `radius` | base corner scale | cards/inputs/buttons/popovers via derived `radius-*` |

- **Radius scale**: `--radius` is the single source of truth; smaller/larger
  radii derive from it (`calc(var(--radius) - Npx)` is the idiomatic form).
- Dark mode = overriding the same tokens inside `.dark`; toggled by class.
- Non-color tokens (`font-sans/serif/mono`, `letter-spacing`, `spacing`,
  shadow tokens) are first-class parts of the preset.

## 2. How theme showcases actually work (tweakcn, shadcn/create, shadcndesign)

- **tweakcn** (<https://tweakcn.com/>, editor + `/community` gallery): live
  preview by writing each theme token onto the root as an inline CSS custom
  property (`document.documentElement.style.setProperty('--background', …)`)
  and letting the real shadcn components (React + Tailwind) re-render. Their
  preview applies the raw `shadow-*`, `spacing`, and `letter-spacing` tokens to
  demo elements, not just colors.
- **tweakcn loads Google Fonts dynamically**: its inline theme script extracts
  the first family from `font-sans/serif/mono`, skips system stacks
  (`ui-sans-serif`, `system-ui`, …), and injects
  `https://fonts.googleapis.com/css2?family=…:wght@400&display=swap` links.
  → Fonts are treated as half the theme's identity; a preview without them
  under-sells presets. (Data: across our 36 presets there are 16 distinct
  `font-sans` first-families — Inter, DM Sans, Montserrat, … — vs 15 distinct
  `radius` values and 27 distinct `shadow-sm` values, i.e. shadows/radius/fonts
  are genuinely preset-specific and must drive rendering.)
- **shadcn/create** (official) and **shadcndesign.com/theme-generator**: same
  pattern — visually tweak tokens, preview against real components, export CSS.
- **shadcnblocks.com/themes**: states themes "follow the official shadcn/ui CSS
  variable contract, so they drop straight into TweakCN, StyleGlide, Tinte" —
  i.e. **the token table IS the theme**; tooling interoperates on variables,
  not components. Confirms our passthrough CSS (`out/css/tweakcn/*.css`) is
  already in the standard exchange format.
- Consensus preview structure: sidebar + dashboard-ish demo card with buttons
  (all variants), badges, inputs/selects/switches/checkboxes, a table, tabs,
  alerts, avatars — light/dark toggle always present.

## 3. Theming shadcn without React/Tailwind

- No mainstream precedent found for rendering shadcn *without* Tailwind —
  every tool assumes a React app. The official docs nonetheless define the
  token→component table above, which is implementation-independent.
- Implication for our gallery (stdlib-only Python constraint): hand-written
  plain CSS that follows the official token table above is legitimate —
  fidelity to the *token contract* is what defines a shadcn theme; pixel
  parity with Tailwind output is not achievable or required.

## 4. Terminal / waybar theming conventions (validates adapter design)

- **catppuccin/waybar**: ships ready-made standalone `*.css` theme files (GTK3
  CSS) that users drop into `~/.config/waybar/` and `@import` from
  `style.css`. **No `@define-color` indirection** — direct hex/rgba values
  per module selector (`window#waybar`, `#workspaces button.active`, …).
  Our `WAYBAR_TEMPLATE` (direct hexes, standalone stylesheet) matches this
  exactly.
- **catppuccin/alacritty**: single generated `.toml` palette file users curl
  into `~/.config/alacritty/`; generated from a template with a palette table.
  Matches our `[colors.*]` quoted-hex approach.
- **catppuccin/wezterm**: themes are `.lua` files returning config tables
  (often via `wezterm.color.get_builtin_schemes()`). A hand-built palette
  table (`ret.ansi = {...}`, `return ret`) is the standard minimal form.
- **foot**: ini-format `[colors]` sections; community palettes
  (catppuccin-foot etc.) use plain `background = #rrggbb` keys — same shape
  as our `FOOT_TEMPLATE`.
- **paletty.dev** (terminal-scheme generator + gallery, exports to
  Ghostty/Kitty/Alacritty/WezTerm/Foot/iTerm2): confirms the ecosystem norm —
  **one canonical palette → many generated per-tool config files**, exactly the
  forge's architecture. Their gallery previews a live terminal, mirroring our
  `terminal_*` token exposure in `out/preview/*.json`.

## 5. Consequences adopted into the build plan

1. Gallery embeds all 36 presets scoped under `html[data-preset=…]`; the
   dropdown rewrites one attribute (tweakcn's setProperty trick, expressed as
   attribute-scoped CSS since all presets share one document).
2. Component CSS follows the official token→component table (§1) — e.g. ghost
   button hover = `--accent`, outline button border = `--input`, focus =
   `--ring` outline, active sidebar item = `--sidebar-primary`.
3. Shadows rendered from `var(--shadow-sm|md|lg|xl|2xl)` (27 distinct
   values across presets); corner radii from `calc(var(--radius) …)`;
   sizes/spacing from `calc(var(--spacing) * N)`.
4. **Google Fonts injection**: parse first non-system family from
   `font-sans/serif/mono`, inject `<link>` on preset change — graceful
   fallback to system fonts offline (`file://` safe). Mirrors tweakcn §2.
   Only deviation from strict offline-self-containment, and deliberate.
5. Waybar adapter keeps direct hexes + standalone stylesheet (§4) — no
   changes needed to the already-shipped template.
6. Token contract remains the interchange format (§2, shadcnblocks) —
   `out/css/tweakcn/*.css` stays canonical; the gallery is a viewer, not a
   new format.

## Sources

- shadcn/ui theming docs — https://ui.shadcn.com/docs/theming
- tweakcn + inline theme script — https://tweakcn.com/ , https://tweakcn.com/community , https://tweakcn.com/editor/theme
- shadcnblocks themes — https://www.shadcnblocks.com/themes
- shadcndesign theme generator — https://www.shadcndesign.com/theme-generator
- shadcn studio — https://shadcnstudio.com/theme-generator
- catppuccin/waybar — https://github.com/catppuccin/waybar
- catppuccin/alacritty — https://github.com/catppuccin/alacritty
- catppuccin/wezterm — https://github.com/catppuccin/wezterm
- paletty.dev — https://github.com/ivoronin/paletty.dev
- Show HN: shadcn theme editor — https://news.ycombinator.com/item?id=45706487

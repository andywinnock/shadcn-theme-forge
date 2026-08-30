# Design

## Source of truth

- Status: Active
- Last refreshed: 2026-08-29
- Primary product surfaces:
  - The live Niri/Noctalia desktop: bar, launcher, Control Center, calendar, notifications, OSD, dock, lock/session surfaces, settings, utilities, and desktop widgets.
  - Qt, GTK, terminal, and compositor-adjacent application chrome that must feel like one desktop system.
  - An offline, responsive shadcn/ui theme gallery for inspecting all generated presets in light and dark modes.
  - A semantic component-and-state specimen board used to create and evaluate assets for a full UI retheme.
  - Native Noctalia outputs and adapters generated from the same source tokens for desktop, terminal, GTK, and Waybar consumers.
- Evidence reviewed:
  - `forge.py`: stdlib-only compiler from tweakcn/shadcn `cssVars` to passthrough CSS and Noctalia palettes.
  - `templates.py`: semantic token expansion and native Noctalia template adapters.
  - `registry.json`: cached source of truth for 36 tweakcn presets.
  - `out/index.json`: generated catalog containing the 36 theme names, titles, and descriptions.
  - `out/css/tweakcn/*.css`: generated light/dark shadcn variables, including typography, radius, spacing, shadow, chart, and sidebar tokens.
  - `out/preview/*.json`: expanded semantic token maps for native template rendering.
  - `out/templates/*`: GTK, terminal, and Waybar adapter templates.
  - `mapping.md`: documented shadcn-to-Noctalia role mapping and intentional semantic compromises.
  - `docs/research-theme-gallery-conventions.md`: ecosystem research covering the official token-to-component contract, showcase conventions, typography/radius/shadow fidelity, and native adapter formats.
  - `CLAUDE.md`: existing pipeline, constraints, and output-layout documentation.
  - Active Noctalia 5 configuration and the upstream compiled-shell/plugin architecture.
  - No existing web UI, component library, screenshots, brand assets, or visual-regression baselines were present when this contract was created.
- Evidence labels:
  - Observed: 36 presets, light/dark CSS selectors, semantic tokens, native adapters, and a Python-standard-library-only toolchain already exist.
  - Approved intent: build a self-contained gallery covering shadcn components and states, then use it to create assets for a full native retheme.
  - Design inference: the gallery should read as a precise theme specimen lab, not as a branded marketing site, so its persistent chrome must remain visually subordinate to the selected preset.

## Brand

- Personality: Exacting, tool-like, expressive through the selected theme, and quietly confident. The shell feels like a color lab or instrument panel; the specimens feel like a real product UI.
- Trust signals: Visible theme name and mode, faithful semantic token use, deterministic output, side-by-side states, legible token labels, clear contrast/focus behavior, and honest indication when a token or font falls back.
- Avoid:
  - Editorial cream/serif/terracotta styling, purple-on-white gradients, ornamental hero sections, and generic SaaS dashboards.
  - Shell colors that compete with or distort the active preset.
  - Hand-tuned per-theme component overrides that conceal weaknesses in the semantic token contract.
  - Decorative animation, glass effects, or shadows not driven by the selected theme.
  - Remote fonts, icon CDNs, analytics, or network-dependent assets.

## Product goals

- Goals:
  - Deliver a cohesive shadcn-derived desktop system across Noctalia and supported applications, with macOS-like consistency of hierarchy and behavior without copying macOS ornamentation.
  - Map semantic component properties—not only colors—into native surfaces: typography, density, spacing, radii, borders, elevation, interaction states, and motion.
  - Make theme and mode changes propagate predictably across the shell and applications without competing configuration sources.
  - Make every one of the 36 presets inspectable without a server, build step, or network connection.
  - Demonstrate whether each preset can drive a coherent, full shadcn-style interface in both light and dark modes.
  - Expose the components, variants, interaction states, content densities, charts, and sidebar patterns needed to author future native retheme assets.
  - Keep web specimens and native Noctalia adapters grounded in the same semantic source tokens.
  - Make regressions and weak mappings visually obvious rather than masking them.
- Non-goals:
  - Reimplementing the full shadcn/ui package or React runtime.
  - Shipping a general-purpose design tool, code editor, theme marketplace, or theme-authoring backend.
  - Pixel-matching the original tweakcn preview site.
  - Mutating the registry or writing to user configuration from the gallery; installation remains a separate explicit, transactional command.
  - Pretending palette-only adapters constitute a native component retheme.
  - Pixel-copying macOS; the target is system coherence, not Apple branding or proprietary assets.
  - Making every preset look alike; preserving meaningful differences is a feature.
- Success signals:
  - The bar, launcher, Control Center/calendar, dock, notifications, OSD, and lock/session surfaces share a recognizable component grammar beyond color alone.
  - Qt, GTK, and terminal test applications visibly follow the active mode and semantic palette with readable contrast.
  - A single theme activation removes or supersedes conflicting theme includes and reports the effective source for each supported surface.
  - A user can choose any preset, switch mode, navigate the specimen groups, and inspect all required states using keyboard or pointer only.
  - All visible specimen colors, radii, shadows, spacing, and typography derive from the selected preset's tokens or documented semantic fallbacks.
  - The gallery loads directly from local files, performs no network requests, and remains usable at phone, tablet, laptop, and wide-desktop sizes.
  - Theme switching is immediate, deterministic, and does not cause layout breakage or unreadable shell controls.
  - The same token decisions can be traced from a web specimen to Noctalia/native output roles.

## Personas and jobs

- Primary personas:
  - Theme author: evaluates and adjusts semantic tokens before generating native assets.
  - Desktop rethemer: checks how shadcn semantics translate to Noctalia, GTK, terminals, and Waybar.
  - UI implementer/reviewer: audits component coverage, responsive behavior, accessibility, and regressions across presets.
- User jobs:
  - Compare how a preset behaves across real component families, not just color swatches.
  - Inspect light and dark parity and identify missing, overloaded, or low-contrast semantic roles.
  - Capture stable reference views for downstream asset work and visual review.
  - Understand which shadcn token drives each native or web surface.
- Key contexts of use: Local development, offline review, narrow laptop windows, wide comparison displays, keyboard-heavy inspection, and screenshot capture.

## Information architecture

- Primary navigation:
  - Persistent utility bar: product name, theme selector, light/dark toggle, and a compact current-theme status.
  - Specimen section navigation: Overview, Actions, Forms, Overlays, Data, Navigation, Feedback, and Tokens.
  - On narrow screens, section navigation becomes a horizontally scrollable tab list or disclosed menu while theme and mode remain directly reachable.
- Core routes/screens:
  - One offline gallery document; no router or multi-page dependency is required.
  - Overview: theme identity, semantic palette, type, radius, spacing, and shadow samples.
  - Actions: button variants, icon buttons, links, segmented actions, and command affordances.
  - Forms: inputs, textarea, select-like controls, checkbox, radio, switch, slider, validation, and help text.
  - Overlays: dialog, popover, dropdown/menu, tooltip, sheet/drawer, and toast specimens.
  - Data: cards, badges, table, pagination, skeletons, progress, charts, and dense/comfortable rows.
  - Navigation: tabs, breadcrumb, pagination, sidebar, command/search, and active/inactive navigation items.
  - Feedback: alert, destructive confirmation, empty state, loading, success, warning, error, and disabled examples.
  - Tokens: named swatches and compact metadata for semantic roles, chart colors, typography, spacing, radius, and shadows.
  - Shell: Noctalia/Niri compositions for the bar, launcher, Control Center, notifications/OSDs, dock, lock screen, settings, wallpaper and clipboard utilities, session controls, and desktop widgets.
- Content hierarchy:
  1. Theme and mode context.
  2. Selected specimen group and its purpose.
  3. Realistic component composition.
  4. Explicit variant/state matrix.
  5. Token trace or compact metadata where it aids diagnosis.

## Design principles

- Principle 1 — Theme fidelity over shell personality: The selected preset controls specimens; persistent gallery chrome uses a restrained graphite laboratory palette (`#0B0D10`, `#15191F`, `#252B33`, `#F4F7FA`, accent `#38D6B3`) and must not leak into specimen styling.
- Principle 2 — Composition over isolated swatches: Show tokens in believable product surfaces, then provide token details as diagnostic support.
- Principle 3 — States are first-class assets: Hover, focus-visible, active, selected, checked, open, disabled, loading, invalid, destructive, and success states receive equal coverage with default states.
- Principle 4 — Semantic ownership stays visible: Components consume shadcn semantic variables; native role mappings remain documented fallbacks rather than silent per-preset fixes.
- Principle 5 — Offline is a product property: Every control, icon, font asset, and interaction must function without network access.
- Tradeoffs:
  - A single static document is preferred over framework ergonomics to preserve the zero-dependency, offline contract.
  - The shell may use a compact, darker tool aesthetic even while a light preset is selected; a clear specimen boundary prevents visual contamination.
  - Static simulations are acceptable for complex components, but their keyboard and state behavior must still be real enough to evaluate focus and semantics.
  - Coverage and faithful token rendering take priority over ornamental polish or elaborate motion.

## Visual language

- Color:
  - Gallery shell: near-black `#0B0D10`, raised surface `#15191F`, divider `#252B33`, primary text `#F4F7FA`, secondary text `#98A2AE`, diagnostic accent `#38D6B3`, and error `#FF6B6B`.
  - Specimen canvas: exclusively selected-theme semantic tokens such as `--background`, `--foreground`, `--card`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, chart, and sidebar roles.
  - Shell controls must be distinguishable from specimens through containment and labels, not translucent overlays.
- Typography:
  - Gallery shell: bundled/local-first `Azeret Mono` for labels and controls, with `ui-monospace` only as an offline fallback. If no font file is bundled, the fallback must be documented in the UI rather than fetched remotely.
  - Specimens: consume `--font-sans`, `--font-serif`, and `--font-mono` from each preset. Missing local typefaces fall through to the preset's declared generic family without network access.
  - Type scale is compact and utilitarian in the shell; specimen typography demonstrates heading, body, label, caption, code, and long-form rhythm.
- Spacing/layout rhythm: Shell rhythm uses a 4px base with 8/12/16/24/32px steps. Specimens consume `--spacing` where practical and preserve readable minimum gaps. Use dense controls in chrome, generous separation between specimen groups, and stable alignment for visual comparison.
- Shape/radius/elevation: Shell uses 6px radii, crisp 1px borders, and minimal elevation. Specimens consume `--radius` and theme shadow tokens exactly; no normalization of expressive presets such as neo-brutalism or claymorphism.
- Motion: One restrained 160–220ms reveal when a theme or mode changes, plus 100–160ms control transitions. Animate opacity and transform only; never delay inspection. Disable nonessential motion under `prefers-reduced-motion`.
- Imagery/iconography: No decorative imagery. Use small, purpose-built inline SVG icons with `currentColor`, consistent 1.75px strokes, accessible names where meaningful, and `aria-hidden` where redundant. Data visualizations use chart tokens and retain text labels/pattern-independent meaning.

## Components

- Existing components to reuse:
  - No web components currently exist.
  - Reuse generated CSS variables in `out/css/tweakcn/*.css`, catalog metadata in `out/index.json`, preview maps in `out/preview/*.json`, and established role mappings in `forge.py`/`templates.py`.
- New/changed components:
  - Shell: utility bar, native theme `<select>`, mode toggle, section navigation, preset status, specimen frame, token inspector, and optional copy-value action.
  - Actions: primary, secondary, outline, ghost, destructive, link, icon-only, split, and loading buttons.
  - Forms: text/password/search inputs, textarea, select/listbox specimen, checkbox, radio, switch, slider, field groups, validation, and descriptions.
  - Surfaces/data: card, stat card, badge, avatar, separator, accordion, table, pagination, progress, skeleton, chart, and empty state.
  - Navigation/overlays: tabs, breadcrumb, sidebar, command/search, dropdown, tooltip, popover, dialog, sheet, and toast.
  - Feedback: alert, success/warning/error messages, destructive confirmation, and inline validation.
  - Noctalia shell compositions:
    - Dock: pinned, running, focused, urgent, hover/tooltip, context-menu, drag-target, and auto-hide indicators.
    - Lock/session: clock and date, user identity, password/error states, login action, and suspend/logout/reboot/shutdown actions.
    - Settings: sidebar navigation, search, switches, sliders, selects, color/file affordances, widget editor, and plugin/template cards.
    - Utilities: wallpaper picker, clipboard history, screenshot controls, theme mode, and per-output state.
    - Desktop widgets: clock, calendar, weather, media, volume, system monitor, and edit/drag/resize treatment.
- Variants and states:
  - Every interactive family: default, hover demonstration, focus-visible, active/pressed, selected/checked/open where applicable, and disabled.
  - Async-capable actions: idle, loading/busy, success, and failure.
  - Inputs: empty, populated, placeholder, focus-visible, invalid, disabled, and read-only.
  - Navigation: inactive, hover, active/current, focus-visible, collapsed where applicable, and notification/badge state.
  - Overlays: closed/open triggers, initial focus, escape/close action, backdrop, and destructive emphasis where applicable.
- Token/component ownership:
  - Preset source tokens own all specimen styling. Components may derive a documented fallback only when a semantic variable is absent.
  - Shell tokens are namespaced (for example `--forge-*`) and never referenced inside specimen component rules.
  - Theme metadata and selection logic own which generated preset stylesheet is active; component markup must not branch by preset name.
  - The Noctalia mapping layer owns native role translation; gallery code must not redefine native mappings.

## Accessibility

- Target standard: WCAG 2.2 AA for the gallery shell and all operable examples. Theme specimens expose contrast failures rather than silently recoloring source presets; diagnostics should flag failures when feasible.
- Keyboard/focus behavior:
  - All controls are reachable in logical DOM order with visible `:focus-visible` treatment.
  - Tabs, menus, dialogs, listboxes, and composite widgets follow expected keyboard patterns; Escape closes dismissible overlays and focus returns to the trigger.
  - Theme and mode switching never loses focus or resets the current specimen section.
- Contrast/readability:
  - Shell text and controls meet AA contrast against their fixed shell surfaces.
  - Specimen text uses paired semantic foreground tokens. Token diagnostics distinguish source contrast from shell compliance.
  - Content remains readable at 200% zoom and with browser text spacing overrides.
- Screen-reader semantics:
  - Use native controls and landmarks first: `header`, `nav`, `main`, `section`, headings, `button`, `select`, `table`, and form labels.
  - Icon-only actions have accessible names; decorative SVGs are hidden.
  - Theme/mode changes update a polite live region without repeatedly announcing unrelated content.
  - Dialogs and status messages use appropriate roles and names; tables retain real headers and captions.
- Reduced motion and sensory considerations:
  - Honor `prefers-reduced-motion: reduce` by removing reveal and transform animations.
  - Never encode state by color alone; pair color with text, iconography, shape, or position.
  - Avoid persistent flashing, parallax, autoplay, and animation required to understand content.

## Responsive behavior

- Supported breakpoints/devices:
  - Small: 320–639px, touch-first phones and narrow windows.
  - Medium: 640–1023px, tablets and compact laptop panes.
  - Large: 1024–1439px, standard desktop working view.
  - Wide: 1440px and above, side-by-side specimen/state comparison.
- Layout adaptations:
  - Small: utility bar wraps into two compact rows; theme selector stays full-width; section navigation scrolls horizontally; specimen grids collapse to one column; tables scroll within labeled containers.
  - Medium: two-column component matrices where useful; tokens remain below specimens.
  - Large: persistent section rail or sticky tabs and two-to-three-column specimen grids.
  - Wide: content width is capped for readability while state matrices may expand; avoid stretching individual controls merely to fill space.
  - Sticky chrome must not cover focused elements or anchors.
- Touch/hover differences:
  - Minimum touch target is 44×44 CSS pixels for primary controls; compact diagnostic affordances may be 32px only when an adjacent full-size target provides the same action.
  - Hover-only demonstrations also expose a labeled persistent sample or keyboard-triggerable equivalent.
  - Tooltips supplement visible labels and are never the sole source of required information.

## Interaction states

- Loading: The static shell has no startup spinner. Async specimen examples use theme-driven skeleton/progress and `aria-busy`; theme switching completes synchronously or shows a brief nonblocking status.
- Empty: Demonstrate a realistic zero-results or no-items composition with a clear next action; do not use an empty blank card.
- Error: Provide inline field error, page-level alert, and destructive operation examples. Errors explain recovery in plain language and do not discard input.
- Success: Use a concise inline confirmation or toast with text/icon reinforcement; preserve the user's current section and focus.
- Disabled: Disabled controls remain legible and are not focusable when natively disabled. Explanatory copy appears nearby when the reason is not obvious.
- Offline/slow network, if applicable: The product is offline by design. No control may require a network request. Missing local theme or font assets produce a contained fallback message while the remaining gallery stays operable.

## Content voice

- Tone: Compact, direct, diagnostic, and free of marketing language.
- Terminology:
  - Use “preset” for one of the 36 tweakcn source themes, “theme” for the active rendered configuration, “mode” for light/dark, “token” for a semantic variable, “specimen” for a rendered UI example, and “adapter” for a native output target.
  - Use shadcn token names verbatim in diagnostic views and Noctalia role names verbatim when showing mappings.
- Microcopy rules:
  - Labels name the action or state (“Switch to dark mode”, “Primary / loading”), not visual placement (“button above”).
  - Descriptions explain what is being tested, not what is self-evident on screen.
  - Show explicit fallback or contrast status without implying that the source preset was modified.
  - Avoid lorem ipsum; use short, realistic product copy that exercises truncation, wrapping, validation, and empty states.

## Implementation constraints

- Framework/styling system:
  - Current repository has no frontend framework or package manifest. Implement as static, standards-based HTML, CSS, and vanilla JavaScript generated or served from repository files.
  - Add no runtime or build dependencies. Do not require React, Tailwind, npm, a local server, or network access to inspect the gallery.
  - Prefer native HTML elements and small progressive-enhancement functions over custom widget abstractions.
  - Noctalia 5 is a compiled C++ shell. Core component replacement requires a reproducible repo-owned source build or upstreamable patch; Luau plugins may extend features but must not be misrepresented as a core skin API.
  - Never patch `/usr/bin/noctalia` in place. Install native builds to a user-owned prefix and preserve a tested rollback to the packaged binary.
  - Prefer supported Noctalia configuration for composition and behavior; fork only where component geometry or rendering cannot be expressed by configuration.
- Design-token constraints:
  - Use `forge.web_mode_tokens()` as the canonical web-theme normalization path for both generated CSS and the gallery. The gallery may embed those effective light/dark maps at authoring time to remain self-contained under `file://`, but must not implement a second merge/cascade algorithm.
  - Preserve OKLCH values, alpha, radius, spacing, shadows, chart tokens, sidebar tokens, and declared typography without converting the web specimen path through Noctalia hex mappings.
  - Namespace shell variables and prevent inheritance into the specimen root except for explicitly selected preset variables.
  - Components consume semantic names, never hard-coded preset values and never preset-name selectors.
  - Document every fallback for a missing semantic token in one central mapping table.
- Performance constraints:
  - Initial interaction should be available within 1 second on a typical local laptop; theme switching should complete within one animation frame where practical and under 100ms at the 95th percentile locally.
  - Only the active preset's properties may be applied to the specimen root. Embedding the compact canonical payloads for all presets in the self-contained artifact is acceptable; do not create 36 simultaneously active stylesheet rule sets or render 36 specimen trees.
  - Avoid layout thrashing, large embedded bitmaps, and continuously running animation.
- Compatibility constraints:
  - Must work from a local checkout without internet access in current evergreen Chromium, Firefox, and Safari.
  - Core content and theme selection should remain usable when opened as a local file. If browser `file://` fetch restrictions prevent data loading, embed or generate the manifest at authoring time rather than requiring a server.
  - Progressive enhancement: specimens and token labels remain visible if JavaScript fails; interactive switching may fall back to a documented default preset.
  - Native adapter generation remains Python 3 standard-library-only and outside the gallery's mutation surface.
  - The live target is Noctalia 5 on Niri. GTK/libadwaita limitations and Qt platform-theme behavior must be documented and verified with representative applications rather than inferred from generated files.
- Test/screenshot expectations:
  - Validate every preset in both modes for stylesheet activation, required semantic variables, uncaught console errors, and overflow at all four breakpoint classes.
  - Run keyboard navigation, focus restoration, semantic/ARIA checks, reduced-motion, forced-colors sanity, and 200% zoom checks.
  - Capture deterministic reference screenshots for at least one neutral, one saturated, one high-expression, and one dark-first preset in both modes at small and large widths; expand to all presets when establishing regression baselines.
  - Confirm the gallery makes zero network requests and works after disconnecting the network.
  - Keep native adapter verification separate: render all supported templates with representative light and dark palettes and fail on unresolved placeholders.
  - Capture live desktop evidence for bar, launcher, Control Center/calendar, dock, notification/OSD, and lock/session surfaces in both modes.
  - Verify effective runtime colors/configuration for Kitty, one GTK3 application, one libadwaita application, and one Qt application; file existence alone is insufficient.
  - Validate packaged-Noctalia rollback before activating a repo-owned native build.

## Implementation acceptance criteria

- [ ] The live desktop visibly implements the documented component grammar across bar, launcher, Control Center/calendar, dock, notifications/OSD, and lock/session surfaces; palette-only changes do not satisfy this criterion.
- [ ] A canonical component mapping covers shadcn surface, card, button, input, menu, popover, dialog, list, tabs, badge, progress, focus, disabled, destructive, and selected states in Noctalia-native terms.
- [ ] Typography, spacing, radii, borders, elevation, density, and motion derive from documented native tokens in addition to semantic colors.
- [ ] Theme and mode changes update every supported live surface through one activation path, without duplicate or later-overriding Kitty/GTK/Qt theme sources.
- [ ] The native Noctalia implementation is reproducibly buildable/installable in a user-owned prefix and can roll back to `/usr/bin/noctalia` without data loss.
- [ ] Representative Qt, GTK3, libadwaita, and terminal applications have evidence-backed behavior and documented toolkit limitations.

- [ ] A single offline gallery entry point opens from a clean checkout without installation, build, or server startup.
- [ ] The theme selector lists exactly the presets present in the generated manifest (currently 36) and never duplicates theme metadata manually.
- [ ] Selecting any preset activates its generated shadcn variables and preserves the current specimen section.
- [ ] Light and dark modes work for every preset; the toggle has an accessible name, visible state, and keyboard operation.
- [ ] The gallery contains the Overview, Actions, Forms, Overlays, Data, Navigation, Feedback, and Tokens specimen groups described above.
- [ ] The Shell specimen covers the Noctalia bar, launcher, Control Center, notifications/OSDs, dock, lock/session surfaces, settings, wallpaper/clipboard utilities, and desktop-widget edit states.
- [ ] Niri-owned overview and window-management visuals remain integration fixtures rather than being represented as Noctalia-owned widgets.
- [ ] Required default, hover sample, focus-visible, active/selected, disabled, loading, invalid/error, destructive, success, empty, and open/closed states are represented where applicable.
- [ ] Specimen rules use semantic variables only; an automated/static audit finds no preset-name styling branches or theme-specific color literals in specimen CSS.
- [ ] Shell rules use namespaced `--forge-*` variables and do not alter active preset token values.
- [ ] Native semantic elements, landmark structure, labels, keyboard behavior, overlay focus management, and screen-reader announcements satisfy the Accessibility contract.
- [ ] Layout has no unintended page-level horizontal overflow at 320px, 768px, 1024px, and 1440px; dense tables use contained scrolling.
- [ ] Reduced-motion mode removes nonessential animation, and all required state meaning survives without color or motion.
- [ ] No remote URL, CDN, telemetry endpoint, or dynamic network dependency is referenced or requested at runtime.
- [ ] Missing font assets and missing optional tokens degrade to documented local fallbacks without breaking layout or interaction.
- [ ] Theme switching causes no uncaught console error and completes in under 100ms locally under the defined test conditions.
- [ ] Reference screenshots and validation results are reproducible from repository commands or a documented manual checklist.
- [ ] Changes to the semantic mapping remain synchronized with `mapping.md`, `forge.py`, `templates.py`, and representative native renders.

## Assumptions

- The current 36-item cached registry remains the authoritative initial theme set, while the gallery derives its list dynamically enough to accept future generated presets.
- The first gallery version is an inspection and asset-authoring surface, not an editor; copying token values is acceptable, but changing/saving themes is out of scope.
- Generated theme CSS remains the authoritative web rendering path; Noctalia conversions are previews of native consumers, not inputs back into web components.
- A self-contained static implementation is preferred over adopting shadcn's React components because the repository's existing contract is dependency-free and offline.
- It is acceptable for unavailable named fonts to use declared generic fallbacks; bundling an openly licensed local font may be considered separately without adding a runtime dependency.
- Representative screenshot baselines can begin with Graphite, Cyberpunk or Doom 64, Claymorphism or Neo Brutalism, and Cosmic Night before full 36-preset coverage is automated.
- Graphite dark is the first native reference implementation; other presets inherit the same component mapping after that vertical slice is qualified.
- Noctalia configuration remains the composition layer while a minimal maintained source patch owns component rendering that configuration cannot express.

## Open questions

- [ ] Decide whether the first release needs side-by-side comparison of two presets or only one active preset / owner: product owner / impact: layout complexity and performance.
- [ ] Decide whether token diagnostics should calculate and display contrast ratios or only expose paired swatches / owner: accessibility reviewer / impact: scope of gallery logic.
- [x] Full-retime shell coverage is defined as current Noctalia surfaces on Niri: bar, launcher, Control Center, notifications/OSDs, dock, lock/session, settings, wallpaper/clipboard/screenshot utilities, and desktop widgets. Niri overview/window management remains theme-adjacent integration coverage rather than a generated Noctalia widget.
- [ ] Decide whether a bundled offline shell font is desired and confirm its license; otherwise use the documented local-first fallback / owner: design owner / impact: shell identity and repository size.
- [ ] Define the canonical screenshot harness and storage location once implementation files exist / owner: implementation owner / impact: repeatable visual regression testing.
- [ ] Decide whether native mapping diagnostics belong in the first gallery or a later inspector panel / owner: product owner / impact: first-release density and complexity.
- [ ] Determine the smallest maintainable Noctalia 5 source patch boundary after auditing upstream component/style primitives / owner: implementation owner / impact: upgrade and packaging cost.
- [ ] Select representative installed Qt and libadwaita applications for repeatable live screenshots / owner: QA owner / impact: cross-toolkit evidence.

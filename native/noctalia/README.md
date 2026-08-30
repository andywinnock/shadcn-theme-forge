# Native Noctalia profile

This directory owns the component-level shadcn mapping for Noctalia 5. It is
separate from the palette/template adapters: those map semantic colors into
consumer formats, while this patch maps geometry, density, focus, and motion
into Noctalia's shared native controls.

The source baseline is pinned in `build_native.sh`. The build installs under
`out/native/noctalia-root`; it never overwrites the packaged
`/usr/bin/noctalia`.

```bash
native/noctalia/build_native.sh
out/native/noctalia-root/bin/noctalia --version
```

The real lock composition can be verified without locking the active session
by running it inside an isolated nested Niri compositor:

```bash
native/noctalia/verify_lock_nested.sh 45 /tmp/shadcn-nested-lock.png dark
native/noctalia/verify_lock_nested.sh 45 /tmp/shadcn-nested-lock-light.png light
```

The virtual compositor uses a temporary runtime and copied configuration; its
session-lock protocol never targets the parent Niri session. The second
argument receives a screenshot of the isolated locked framebuffer.

## Graphite component mapping

| shadcn concept | Noctalia primitive |
| --- | --- |
| compact/default/large radius | `Style::radiusSm/Md/Lg` |
| card/dialog radius | `Style::radiusXl` |
| spacing scale | `Style::spaceXs/Sm/Md/Lg` |
| card/panel inset | `Style::cardPadding/panelPadding` |
| compact/default/large control | `Style::controlHeightSm/controlHeight/controlHeightLg` |
| border | `Style::borderWidth` |
| focus-visible ring | `Style::focusRingWidth` |
| fast/default/slow motion | `Style::animFast/Normal/Slow` |

Graphite uses a 4/8/12/16 radius scale, 4/8/12/16 spacing scale, 16px surface
insets, 32/40/44px controls, 1px borders, 2px focus rings, and restrained
120/180/280ms motion. Color ownership remains in the generated Noctalia
palette so all presets reuse this component grammar.

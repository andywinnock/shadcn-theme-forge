# shadcn/tweakcn -> noctalia role mapping (v1)

Source tokens: tweakcn `cssVars.dark|light` (oklch). Target: noctalia
palette JSON roles (Material-flavored) + passthrough CSS.

| noctalia role | shadcn source (in priority order)                     | intent                        |
|---------------|------------------------------------------------------|-------------------------------|
| primary       | primary                                              | accent, buttons               |
| onPrimary     | primary-foreground                                   |                               |
| secondary     | ring -> accent-foreground?                           | second accent (see note 1)    |
| onSecondary   | secondary-foreground                                 |                               |
| tertiary      | chart-2                                              | third accent from charts      |
| onTertiary    | chart-2-on? not present -> contrast L rule           |                               |
| error         | destructive                                          |                               |
| onError       | destructive-foreground                               |                               |
| surface       | background (dark); card for elevated (unused in v1)  | shell background              |
| onSurface     | foreground                                           |                               |
| surfaceVariant| muted                                                | cards/inputs/inactive         |
| onSurfaceVariant | muted-foreground                                  | secondary text — sets "feel"  |
| outline       | border                                               | hairlines                     |
| shadow        | shadow-color (fallback: background)                  |                               |
| hover         | accent                                               | shadcn hover = accent surface |
| onHover       | accent-foreground                                    |                               |
| terminal.*    | black=shadow? see code; fg=foreground bg=background; |                               |
|               | colors 1-6 = chart-1..5 + secondary                  |                               |

## Notes

1. **secondary collision.** shadcn `secondary` is a *neutral surface*, not an
   accent; noctalia `secondary` is an accent role. Mapping neutral->accent would
   mute noctalia's accents; instead use `ring` (focus hue, usually near primary)
   — honest divergence, documented.
2. **onX colors** mostly exist in shadcn (`*-foreground`); where absent,
   derive by L: pick #ffffff or #000000 whichever has higher WCAG contrast.
3. **Charts -> terminal:** chart-1..5 fill ANSI colors 1-5 (red..magenta..blue
   order per chart-1=primary-ish? keep chart order), + destructive red, primary.
   ANSI 0/7 black/white from shadow/foreground ramp.
4. `input` token intentionally unused (noctalia has no input-border role;
   outline covers it).

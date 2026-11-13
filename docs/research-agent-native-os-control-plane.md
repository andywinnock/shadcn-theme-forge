# Agent-native OS control plane for Niri and Noctalia

Research date: 2026-08-29

## Verdict

The semantic-first version is practical today. The product should be a small,
local capability broker between an agent and the desktop—not an LLM with raw
access to Niri, D-Bus, Wayland, a shell, or `sudo`.

This host already has the key substrate:

- Niri 26.04 runs as the Wayland compositor and exposes structured JSON state,
  a state-first event stream, and typed actions.
- Noctalia v5.0.0 beta runs as the shell and exposes semantic commands for its
  panels, dock, widgets, clipboard, media, power, network, brightness,
  screenshots, settings, themes, wallpaper, notifications, and plugins.
- PipeWire, the desktop portal, GNOME-compatible screen-cast services, the
  accessibility manager, and the user D-Bus are active.
- The local shell/QML tree already contains bar, dock, launcher, workspace,
  power, wallpaper, and overview modules.

The current theme forge should remain the design/token compiler. Agent control
belongs in a companion daemon with a narrow contract; Noctalia should provide
the visible status and approval surface.

## Proposed architecture

```text
Local LLM / agent host
        |
        | typed MCP tools
        v
agent-desktopd -- hardened systemd user service
        |
        +-- policy engine and capability manifest
        +-- append-only, content-redacted audit log
        +-- Niri adapter: state graph, event stream, compositor actions
        +-- Noctalia adapter: shell state and semantic shell actions
        +-- D-Bus adapters: MPRIS, UPower, NetworkManager, BlueZ
        +-- application adapters: CDP, native CLIs/APIs, AT-SPI
        +-- portal adapter: consented PipeWire capture plus EIS input
        |
        v
Noctalia Agent panel
intent, plan, approvals, active capability indicator, revoke/kill switch
```

The broker maintains a live graph of output -> workspace -> window from Niri's
event stream. Agent tools operate on stable IDs and explicit preconditions,
rather than coordinates inferred from pixels.

Initial tool contract:

```text
desktop.get_state()
desktop.list_windows()
desktop.focus_window(window_id)
desktop.move_window(window_id, workspace_id)
shell.get_status()
shell.open_panel(panel_id, context?)
media.play_pause(player_id)
capture.request_session(target, devices)
```

The contract must not include `run_shell`, arbitrary D-Bus calls, a raw
Wayland/Niri socket, or a generic privileged-command tool.

## Control hierarchy

Use the highest-semantic interface available:

1. Application-native API, protocol, or CLI.
2. Niri or Noctalia typed IPC.
3. Dedicated D-Bus adapter.
4. Browser DevTools Protocol for browser content.
5. AT-SPI accessibility semantics where an application exposes them well.
6. Portal-mediated screen capture and input injection as a visible fallback.

This order makes actions inspectable, testable, auditable, and recoverable.
Screenshot-and-click automation remains useful, but should be treated as the
last adapter rather than the foundation.

## Capability and approval tiers

| Tier | Examples | Default policy |
| --- | --- | --- |
| Read-only | desktop graph, battery, current media, shell status | Automatic and logged |
| Reversible desktop control | focus window, change workspace, open panel | Allowlisted and logged |
| Sensitive user data | clipboard read, screenshot, cast, notification history | Per-action approval |
| External effect | network changes, Bluetooth pairing, messaging, deletion | Human-readable diff and approval |
| Privileged/system | packages, mounts, system services, privileged files | Separate helper; never raw LLM control |

Locking the session should immediately revoke capture, injected input, clipboard
access, and every mutation capability. The Noctalia bar should show an
unmistakable indicator while sensitive capabilities are active and expose a
one-action revoke switch.

Audit entries should include the requested tool, capability tier, target IDs,
preconditions, approval ID, outcome, and a redacted reason. Clipboard contents,
screenshots, typed text, and secrets should not be logged by default.

## Screen and input fallback

Use the XDG Remote Desktop and ScreenCast portals. They deliberately mediate
consent, provide PipeWire streams, and support EIS/libei input. A fallback loop
can be:

```text
request selected-window session
-> capture frame
-> identify target
-> display proposed click/type plan
-> approve
-> inject constrained input through EIS
-> verify semantic state or a second frame
```

Do not use kernel `uinput` for normal operation. It creates a system-wide
virtual input device and grants a broader capability than this design needs.

## Limits and genuine blockers

- Linux has no universal semantic application-control API. Strong compositor
  and shell control is available now; application control still needs adapters.
- Noctalia v5's plugin API is beta. Pin its version and keep policy enforcement
  in the external broker, not in a plugin.
- Niri's accessibility tree is not a universal automation tree.
- Portal input and screen access are intentionally consent-gated and must not be
  bypassed.
- MCP is a tool-description and transport contract, not a security boundary.
- Downloaded skills and plugins must run outside the trusted broker and without
  direct access to desktop sockets.

## Prototype plan

### Phase 0: contract and threat model

- Define typed tools, capability tiers, approval rules, redaction, and lock-time
  revocation.
- Define a versioned adapter interface and structured error vocabulary.

### Phase 1: read-only native desktop model

- Create `agent-desktopd` as a hardened `systemd --user` service.
- Subscribe to `niri msg --json event-stream`.
- Read `noctalia msg status`.
- Expose only `desktop.get_state`, `desktop.list_windows`, and
  `shell.get_status` over a local MCP server.
- Write JSONL audit events containing metadata but no captured content.
- Add a Noctalia Agent panel showing the live desktop graph and broker status.

### Phase 2: reversible semantic actions

- Add allowlisted focus, workspace, window-move, panel, dock, and theme actions.
- Require target IDs and preconditions; reject stale plans.
- Add dry-run responses and a visible emergency revoke control.

### Phase 3: system and application adapters

- Add MPRIS and UPower first.
- Add NetworkManager and BlueZ behind explicit approval.
- Add browser/CDP and high-value application adapters.

### Phase 4: vision and input fallback

- Prototype a portal-granted, selected-window PipeWire plus EIS session.
- Keep it visibly active, time-limited, target-constrained, and immediately
  revocable.

## Recommended next slice

Build Phase 0 and Phase 1 only. That proves the central idea—an agent has a
native, continuously updated model of the laptop—without granting click, type,
shell, network, or privileged mutation capabilities.

## Primary references

- [Niri IPC](https://github.com/niri-wm/niri/wiki/IPC)
- [Niri IPC action API](https://niri-wm.github.io/niri/niri_ipc/enum.Action.html)
- [Niri security model](https://github.com/niri-wm/niri/wiki/Security-Model)
- [Niri screencasting](https://github.com/niri-wm/niri/wiki/Screencasting)
- [Noctalia IPC](https://docs.noctalia.dev/noctalia/ipc/)
- [Noctalia plugin development](https://docs.noctalia.dev/noctalia/plugins/development/)
- [Noctalia plugin runtime](https://docs.noctalia.dev/noctalia/plugins/development/runtime-api/)
- [XDG Remote Desktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- [XDG ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)
- [libei](https://libinput.pages.freedesktop.org/libei/)
- [MPRIS](https://specifications.freedesktop.org/mpris/latest/)
- [NetworkManager D-Bus API](https://networkmanager.dev/docs/developers/)
- [UPower D-Bus API](https://upower.freedesktop.org/docs/ref-dbus.html)
- [MCP specification](https://modelcontextprotocol.io/specification/2025-03-26/index)
- [Linux uinput](https://www.kernel.org/doc/html/v4.12/input/uinput.html)

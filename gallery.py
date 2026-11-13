#!/usr/bin/env python3
"""Generate and verify the dependency-free shadcn theme specimen gallery."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from forge import web_mode_tokens
from oklch import css_color_to_hex


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "registry.json"
OUTPUT_PATH = ROOT / "out" / "gallery" / "index.html"
SECTIONS = ("Overview", "Shell", "Actions", "Forms", "Overlays", "Data", "Navigation", "Feedback", "Tokens")
REQUIRED_TOKENS = {"background", "foreground", "primary", "primary-foreground", "border", "input", "ring"}
TOKEN_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")
UNSAFE_TOKEN_VALUE = re.compile(r"[;{}]|url\s*\(|@import|</?(?:style|script)", re.I)
SEMANTIC_TOKENS = (
    "background", "foreground", "card", "card-foreground", "popover", "popover-foreground",
    "primary", "primary-foreground", "secondary", "secondary-foreground", "muted",
    "muted-foreground", "accent", "accent-foreground", "destructive", "destructive-foreground",
    "border", "input", "ring", "chart-1", "chart-2", "chart-3", "chart-4", "chart-5",
    "sidebar", "sidebar-foreground", "sidebar-primary", "sidebar-primary-foreground",
    "sidebar-accent", "sidebar-accent-foreground", "sidebar-border", "sidebar-ring",
)


def load_themes(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    themes = registry.get("items", [])
    if not isinstance(themes, list):
        raise ValueError("registry.json items must be a list")
    if not themes:
        raise ValueError("registry.json contains no theme presets")
    return themes


def theme_payload(theme: dict[str, Any]) -> dict[str, Any]:
    css_vars = theme.get("cssVars", {})
    if not isinstance(css_vars, dict):
        css_vars = {}
    effective_modes = web_mode_tokens(theme)
    modes: dict[str, dict[str, str]] = {}
    for mode in ("light", "dark"):
        values = effective_modes[mode]
        for name, value in values.items():
            if not TOKEN_NAME.fullmatch(name):
                raise ValueError(f"{theme.get('name', '<unnamed>')}: invalid CSS token name {name!r}")
            if not isinstance(value, str) or not value.strip() or UNSAFE_TOKEN_VALUE.search(value):
                raise ValueError(f"{theme.get('name', '<unnamed>')}: unsafe CSS token value for {name!r}")
        missing = REQUIRED_TOKENS - values.keys()
        if missing:
            raise ValueError(f"{theme.get('name', '<unnamed>')}: {mode} mode missing required tokens: {', '.join(sorted(missing))}")
        modes[mode] = values
    diagnostic_tokens = ("background", "muted", "border", "foreground", "primary", "destructive")
    diagnostics = {
        mode: {
            token: (css_color_to_hex(values[token]) or values[token]).upper()
            for token in diagnostic_tokens
        }
        for mode, values in modes.items()
    }
    return {
        "name": str(theme.get("name", "")),
        "title": str(theme.get("title", theme.get("name", "Untitled"))),
        "description": str(theme.get("description", "")),
        "modes": modes,
        "diagnostics": diagnostics,
    }


def declarations(values: dict[str, str]) -> str:
    return ";".join(f"--{name}:{value}" for name, value in values.items())


SHELL_CSS = r"""
:root{--forge-bg:#0b0d10;--forge-panel:#15191f;--forge-line:#252b33;--forge-text:#f4f7fa;--forge-muted:#98a2ae;--forge-accent:#38d6b3;--forge-error:#ff6b6b;color-scheme:dark;font-family:Arial,Helvetica,sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:7rem}body{margin:0;background:var(--forge-bg);color:var(--forge-text)}button,select{font:inherit}.utility{position:sticky;z-index:20;top:0;display:flex;gap:1.35rem;align-items:center;height:62px;padding:.55rem .85rem  .55rem 1.35rem;background:var(--forge-bg);border:1px solid var(--forge-line);border-radius:8px 8px 0 0}.brand{display:flex;align-items:center;gap:.65rem;min-width:175px}.mark{width:.7rem;height:.7rem;background:var(--forge-accent);border-radius:50%;box-shadow:0 0 0 3px #38d6b318}.brand strong{display:block;font-size:1rem;letter-spacing:.02em}.eyebrow,.field-label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}.theme-control{width:216px}.theme-control select,.mode-toggle,.utility-icon{min-height:38px;border:1px solid var(--forge-line);border-radius:6px;background:var(--forge-panel);color:var(--forge-text);padding:.55rem .75rem}.theme-control select{width:100%}.mode-group{display:flex;border:1px solid var(--forge-line);border-radius:6px;padding:2px}.mode-toggle{border:0;cursor:pointer}.mode-toggle:hover,.mode-toggle:focus-visible,.theme-control select:focus-visible,.utility-icon:focus-visible{border-color:var(--forge-accent);outline:2px solid transparent;box-shadow:0 0 0 2px #38d6b344}.utility-spacer{flex:1}.status{color:var(--forge-text);font-size:.75rem;white-space:nowrap}.status::before{content:"";display:inline-block;width:.5rem;height:.5rem;margin-right:.55rem;border-radius:50%;background:var(--forge-accent)}.utility-icon{width:38px;padding:0;cursor:pointer}.section-nav{position:sticky;z-index:15;top:62px;display:flex;gap:.4rem;overflow-x:auto;height:44px;padding:0 1.85rem;background:var(--forge-panel);border-bottom:1px solid var(--forge-line);scrollbar-width:thin}.section-nav a{display:grid;place-items:center;flex:none;color:var(--forge-muted);font-size:.75rem;text-decoration:none;padding:0 .9rem;border-bottom:2px solid transparent}.section-nav a:first-child{color:var(--forge-text);border-color:var(--forge-accent)}.section-nav a:hover,.section-nav a:focus-visible{color:var(--forge-text);outline:none}.gallery-shell{display:grid;grid-template-columns:212px minmax(0,1fr);align-items:start}.gallery-rail{position:sticky;top:106px;height:calc(100vh - 106px);padding:1rem .75rem;background:linear-gradient(135deg,#15191f,#0d1117);border-right:1px solid var(--forge-line);overflow:auto}.rail-label{display:block;margin:.15rem .65rem .55rem;color:var(--forge-muted);font-size:.71rem;letter-spacing:.08em;text-transform:uppercase}.rail-nav{display:grid;gap:.2rem}.rail-nav a{display:flex;align-items:center;gap:.7rem;min-height:38px;padding:.45rem .65rem;border-radius:6px;color:#cbd2da;font-size:.84rem;text-decoration:none}.gallery-rail>.rail-nav:first-of-type a:first-child,.rail-nav a:hover,.rail-nav a:focus-visible{background:#252b33;color:#fff;outline:none}.rail-icon{display:grid;place-items:center;width:20px;color:var(--forge-muted)}.adapter-status-dot{width:8px;height:8px;margin-left:auto;border-radius:50%;background:var(--forge-accent)}.rail-divider{height:1px;margin:1rem 0;background:var(--forge-line)}.rail-foot{position:absolute;bottom:1rem;color:var(--forge-muted);font-size:.65rem;line-height:1.6}.gallery-main{min-width:0;padding:0;background:var(--forge-bg)}.specimen-boundary{overflow:hidden}.boundary-label{display:none}.local-note{color:var(--forge-accent)}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:900px){.utility{flex-wrap:wrap;height:auto}.utility-spacer,.status,.utility-icon{display:none}.section-nav{top:57px}.gallery-shell{grid-template-columns:1fr}.gallery-rail{display:none}.gallery-main{padding:0}}@media(max-width:560px){.brand{min-width:0}.brand strong{overflow-wrap:anywhere}.theme-control{order:3;width:100%;min-width:0}.theme-control select{min-height:44px}.section-nav{position:static}.utility{position:static;gap:.55rem;padding:.55rem}.mode-group{margin-left:auto}.mode-toggle{min-height:44px}.gallery-main,.specimen-boundary{min-width:0}}
.status,.rail-foot,.local-note,.theme-control select{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}.utility-icon,.mode-toggle{display:inline-flex;align-items:center;justify-content:center;gap:.4rem}.icon-svg{display:inline-block;flex:none;width:16px;height:16px;vertical-align:-3px;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round;fill:none}.rail-icon .icon-svg{width:16px;height:16px}
"""


SPECIMEN_CSS = r"""
/* SPECIMEN_CSS_START */
.specimen{color-scheme:light;background:var(--background);color:var(--foreground);font-family:var(--font-sans);letter-spacing:var(--tracking-normal);line-height:1.5;min-height:100vh;transition:background-color 180ms,color 180ms}.specimen[data-theme=dark]{color-scheme:dark}.specimen *{box-sizing:border-box}.specimen button,.specimen input,.specimen textarea,.specimen select{font:inherit}.specimen :focus-visible{outline:2px solid var(--ring);outline-offset:2px}.spec-section{padding:clamp(1rem,3vw,2.5rem);border-bottom:1px solid var(--border);scroll-margin-top:9rem}.section-head{max-width:48rem;margin-bottom:1.5rem}.section-head h1,.section-head h2,.section-head p{margin:0}.section-head h1{font-size:clamp(1.8rem,5vw,3.6rem);line-height:1.05;letter-spacing:var(--tracking-tight)}.section-head h2{font-size:1.4rem}.section-head p{color:var(--muted-foreground);margin-top:.4rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,19rem),1fr));gap:calc(var(--spacing, .25rem)*4)}.stack{display:grid;gap:calc(var(--spacing, .25rem)*3)}.row{display:flex;flex-wrap:wrap;gap:calc(var(--spacing, .25rem)*2);align-items:center}.panel,.card{background:var(--card);color:var(--card-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-sm);padding:1rem}.panel h3,.card h3{margin:0 0 .25rem}.subtle{color:var(--muted-foreground);font-size:.875rem}.label{display:block;font-size:.8125rem;font-weight:600;margin-bottom:.35rem}.state-label{font-family:var(--font-mono);font-size:.6875rem;color:var(--muted-foreground)}.button{display:inline-flex;min-height:40px;align-items:center;justify-content:center;gap:.45rem;padding:.55rem .9rem;border:1px solid transparent;border-radius:var(--radius);background:var(--primary);color:var(--primary-foreground);box-shadow:var(--shadow-xs);cursor:pointer}.button:hover,.button.demo-hover{filter:brightness(.94)}.button:active,.button.demo-active{transform:translateY(1px)}.button.secondary{background:var(--secondary);color:var(--secondary-foreground)}.button.outline{background:var(--background);color:var(--foreground);border-color:var(--input)}.button.ghost{background:transparent;color:var(--foreground);box-shadow:none}.button.ghost:hover,.button.ghost.demo-hover{background:var(--accent);color:var(--accent-foreground);filter:none}.button.destructive{background:var(--destructive);color:var(--destructive-foreground)}.button.link{background:transparent;color:var(--primary);padding-inline:.15rem;box-shadow:none;text-decoration:underline;text-underline-offset:4px}.button.icon{width:40px;padding:0}.button[disabled]{opacity:.5;cursor:not-allowed;transform:none}.spinner{width:1rem;height:1rem;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:spin .7s linear infinite}.field{display:grid;gap:.25rem}.control{width:100%;min-height:42px;padding:.55rem .7rem;color:var(--foreground);background:var(--background);border:1px solid var(--input);border-radius:var(--radius)}textarea.control{min-height:90px;resize:vertical}.control[aria-invalid=true]{border-color:var(--destructive)}.error{color:var(--destructive);font-size:.75rem}.choice{display:flex;gap:.55rem;align-items:center}.choice input{width:1rem;height:1rem;accent-color:var(--primary)}.switch{position:relative;width:44px;height:24px;border:0;border-radius:999px;background:var(--input);padding:2px;cursor:pointer}.switch::after{content:"";display:block;width:20px;height:20px;border-radius:50%;background:var(--background);box-shadow:var(--shadow-xs);transition:transform 140ms}.switch[aria-checked=true]{background:var(--primary)}.switch[aria-checked=true]::after{transform:translateX(20px)}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:.15rem .55rem;background:var(--secondary);color:var(--secondary-foreground);font-size:.75rem}.badge.primary{background:var(--primary);color:var(--primary-foreground)}.badge.destructive{background:var(--destructive);color:var(--destructive-foreground)}.stat{font-size:1.8rem;font-weight:700}.progress{height:.55rem;overflow:hidden;border-radius:999px;background:var(--secondary)}.progress>span{display:block;width:68%;height:100%;background:var(--primary)}.separator{height:1px;background:var(--border);margin:.5rem 0}.skeleton{height:.85rem;border-radius:var(--radius);background:var(--muted);animation:pulse 1.4s ease-in-out infinite}.table-wrap{overflow-x:auto}.data-table{border-collapse:collapse;width:100%;min-width:34rem}.data-table caption{text-align:left;font-weight:600;margin-bottom:.5rem}.data-table th,.data-table td{padding:.7rem;text-align:left;border-bottom:1px solid var(--border)}.data-table th{color:var(--muted-foreground);font-size:.75rem}.chart{display:flex;align-items:end;gap:.6rem;height:9rem;padding-top:1rem}.chart-bar{flex:1;border-radius:var(--radius) var(--radius) 0 0;min-width:1.5rem}.chart-bar:nth-child(1){height:42%;background:var(--chart-1)}.chart-bar:nth-child(2){height:72%;background:var(--chart-2)}.chart-bar:nth-child(3){height:56%;background:var(--chart-3)}.chart-bar:nth-child(4){height:88%;background:var(--chart-4)}.chart-bar:nth-child(5){height:64%;background:var(--chart-5)}.tabs{display:flex;gap:.25rem;border-bottom:1px solid var(--border)}.tab{border:0;background:transparent;color:var(--muted-foreground);padding:.65rem .8rem;border-bottom:2px solid transparent;cursor:pointer}.tab[aria-selected=true]{color:var(--foreground);border-color:var(--primary)}.tab-panel{padding:1rem 0}.breadcrumb{display:flex;gap:.5rem;align-items:center;list-style:none;padding:0}.breadcrumb li+li::before{content:"/";color:var(--muted-foreground);margin-right:.5rem}.sidebar-demo{display:grid;grid-template-columns:12rem 1fr;min-height:15rem;border:1px solid var(--sidebar-border);border-radius:var(--radius);overflow:hidden}.side{background:var(--sidebar);color:var(--sidebar-foreground);padding:.75rem}.side a{display:block;color:inherit;text-decoration:none;padding:.55rem;border-radius:var(--radius)}.side a:focus-visible{outline-color:var(--sidebar-ring)}.side a[aria-current=page]{background:var(--sidebar-primary);color:var(--sidebar-primary-foreground)}.side-content{padding:1rem;background:var(--background)}.alert{padding:.85rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--card-foreground)}.alert strong{display:block}.alert.error-alert{border-color:var(--destructive)}.alert.success-alert{border-color:var(--primary)}.empty{text-align:center;padding:2.5rem 1rem;border:1px dashed var(--border);border-radius:var(--radius)}.menu-wrap,.tooltip-wrap,.popover-wrap{position:relative;display:inline-block}.menu{position:absolute;z-index:5;top:calc(100% + .4rem);left:0;min-width:12rem;padding:.35rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-lg)}.menu[hidden]{display:none}.menu button{display:block;width:100%;padding:.5rem;border:0;border-radius:var(--radius);text-align:left;background:transparent;color:inherit}.menu button:hover,.menu button:focus{background:var(--accent);color:var(--accent-foreground);outline:none}.popover-panel{position:absolute;z-index:4;top:calc(100% + .4rem);right:0;width:16rem;padding:.8rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-lg)}.popover-panel[hidden]{display:none}.sheet{position:fixed;z-index:30;inset:0 0 0 auto;width:min(24rem,90vw);padding:1.25rem;background:var(--popover);color:var(--popover-foreground);border-left:1px solid var(--border);box-shadow:var(--shadow-2xl)}.sheet[hidden]{display:none}.tooltip{position:absolute;left:50%;bottom:calc(100% + .5rem);transform:translateX(-50%);white-space:nowrap;background:var(--foreground);color:var(--background);padding:.3rem .5rem;border-radius:var(--radius);font-size:.75rem;opacity:0;pointer-events:none}.tooltip-wrap:hover .tooltip,.tooltip-wrap:focus-within .tooltip{opacity:1}.dialog{max-width:32rem;width:calc(100% - 2rem);padding:0;border:1px solid var(--border);border-radius:var(--radius);background:var(--popover);color:var(--popover-foreground);box-shadow:var(--shadow-2xl)}.dialog::backdrop{background:color-mix(in oklch,var(--foreground) 40%,transparent)}.dialog-body{padding:1.25rem}.dialog h3{margin-top:0}.toast{display:flex;align-items:flex-start;gap:.75rem;padding:.85rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-lg)}.token-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:.6rem}.token{display:grid;grid-template-columns:2.5rem 1fr;gap:.7rem;align-items:center;padding:.5rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--card)}.swatch{height:2.5rem;border-radius:var(--radius);border:1px solid var(--border)}.token code{font-family:var(--font-mono);font-size:.72rem;overflow-wrap:anywhere}@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{50%{opacity:.45}}@media(max-width:600px){.sidebar-demo{grid-template-columns:1fr}.side{display:flex;overflow-x:auto}.side a{white-space:nowrap}.spec-section{padding:1rem}.button{min-height:44px}}@media(prefers-reduced-motion:reduce){.specimen,.switch::after{transition:none}.spinner,.skeleton{animation:none}}
.shell-overview{padding:1.4rem;min-height:886px}.shell-overview .section-head{display:flex;align-items:flex-start;justify-content:space-between;max-width:none;margin-bottom:1rem}.shell-overview .section-head h1{font-size:1.2rem}.shell-overview .section-head p{font-size:.75rem}.shell-badge{display:inline-flex;align-items:center;gap:.35rem;padding:.35rem .6rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--background);font-size:.7rem}.shell-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr) minmax(220px,.72fr);gap:.75rem}.shell-card{min-width:0;padding:.9rem;background:var(--card);color:var(--card-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-xs)}.shell-card h3{margin:0 0 .65rem;font-size:.82rem}.shell-card h4{margin:.8rem 0 .4rem;font-size:.7rem}.noctalia-bar{grid-column:1/-1;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:.75rem;min-height:46px;padding:.4rem .5rem;background:var(--sidebar);color:var(--sidebar-foreground);border:1px solid var(--sidebar-border);border-radius:var(--radius)}.workspace-list,.system-widgets,.launcher-results,.quick-grid,.notification-stack,.osd-stack{display:flex;gap:.35rem}.workspace-list,.system-widgets{align-items:center}.workspace{width:28px;height:28px;padding:0;border:1px solid transparent;border-radius:var(--radius);background:transparent;color:inherit;font-size:.68rem}.workspace[aria-current=true]{background:var(--sidebar-primary);color:var(--sidebar-primary-foreground)}.active-window{overflow:hidden;text-align:center;text-overflow:ellipsis;white-space:nowrap;font-size:.72rem;color:var(--muted-foreground)}.system-widgets{justify-content:flex-end;font-size:.7rem}.system-pill{padding:.3rem .45rem;border-radius:var(--radius);background:var(--sidebar-accent);color:var(--sidebar-accent-foreground)}.launcher-search{position:relative}.launcher-search .control{padding-left:2rem}.launcher-results{flex-direction:column;margin-top:.55rem}.launcher-item{display:grid;grid-template-columns:30px 1fr auto;gap:.55rem;align-items:center;padding:.45rem;border-radius:var(--radius);font-size:.72rem}.launcher-item:first-child{background:var(--accent);color:var(--accent-foreground)}.app-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:var(--radius);background:var(--primary);color:var(--primary-foreground);font-weight:700}.key{padding:.08rem .3rem;border:1px solid var(--border);border-radius:4px;color:var(--muted-foreground);font-family:var(--font-mono);font-size:.6rem}.quick-grid{display:grid;grid-template-columns:1fr 1fr}.quick-tile{display:grid;grid-template-columns:28px 1fr;gap:.45rem;align-items:center;min-height:50px;padding:.45rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--background);color:var(--foreground);font-size:.68rem}.quick-tile[aria-pressed=true]{background:var(--primary);color:var(--primary-foreground);border-color:var(--primary)}.quick-tile strong,.quick-tile span{display:block}.quick-tile span{opacity:.7;font-size:.6rem}.media-row{display:grid;grid-template-columns:42px 1fr auto;gap:.55rem;align-items:center;margin-top:.65rem;padding:.55rem;background:var(--muted);border-radius:var(--radius);font-size:.68rem}.album{width:42px;height:42px;border-radius:var(--radius);background:linear-gradient(135deg,var(--chart-1),var(--chart-3))}.cc-tabs{display:flex;gap:.25rem;margin-bottom:.6rem;border-bottom:1px solid var(--border)}.cc-tabs button{padding:.35rem;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--muted-foreground);font-size:.62rem}.cc-tabs button[aria-selected=true]{color:var(--foreground);border-color:var(--primary)}.notification-stack,.osd-stack{flex-direction:column}.notification{display:grid;grid-template-columns:28px 1fr auto;gap:.45rem;padding:.55rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--popover);color:var(--popover-foreground);box-shadow:var(--shadow-sm);font-size:.65rem}.notification strong{display:block;font-size:.7rem}.notification p{margin:.1rem 0;color:var(--muted-foreground)}.notif-dot{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--accent);color:var(--accent-foreground)}.notification time{color:var(--muted-foreground);font-size:.58rem}.osd{display:grid;grid-template-columns:22px 1fr auto;gap:.5rem;align-items:center;padding:.55rem;border:1px solid var(--border);border-radius:999px;background:var(--popover);box-shadow:var(--shadow-md);font-size:.65rem}.osd-meter{height:5px;overflow:hidden;border-radius:999px;background:var(--secondary)}.osd-meter span{display:block;height:100%;background:var(--primary)}.osd:nth-child(2) .osd-meter span{width:72%}.osd:first-child .osd-meter span{width:46%}.shell-lower{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem}.metric-row{display:flex;justify-content:space-between;align-items:center;margin-top:.5rem;color:var(--muted-foreground);font-size:.65rem}.metric-row strong{color:var(--foreground)}@media(max-width:1050px){.shell-grid{grid-template-columns:1fr 1fr}.shell-card.notifications{grid-column:1/-1}.shell-lower{grid-template-columns:1fr 1fr}}@media(max-width:700px){.shell-grid,.shell-lower{grid-template-columns:1fr}.noctalia-bar{grid-template-columns:1fr}.active-window{text-align:left}.system-widgets{justify-content:flex-start;flex-wrap:wrap}.shell-card.notifications{grid-column:auto}}
.dashboard-overview{padding:1.25rem;min-height:886px}.dashboard-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1rem}.dashboard-head h1{margin:0;font-size:1.2rem;line-height:1.3}.dashboard-head p{margin:.15rem 0 0;color:var(--muted-foreground);font-size:.72rem}.dashboard-grid{display:grid;grid-template-columns:1.35fr .88fr .56fr;gap:.65rem}.dash-card{min-width:0;padding:.78rem;background:var(--card);color:var(--card-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-xs)}.dash-card h2,.dash-card h3{margin:0 0 .6rem;font-size:.76rem}.dash-card h4{margin:.5rem 0 .25rem;font-size:.64rem}.dash-actions{display:grid;grid-template-columns:1fr 150px;gap:.65rem}.dash-button-row{display:flex;gap:.45rem;align-items:end}.dash-demo{display:grid;gap:.18rem}.dash-demo small,.dash-label{color:var(--muted-foreground);font-size:.58rem}.dash-button{min-height:30px;padding:.35rem .65rem;font-size:.65rem}.dash-states{padding-left:.65rem;border-left:1px solid var(--border)}.dash-state{margin-bottom:.35rem;padding:.38rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.62rem}.dash-state.success{background:color-mix(in oklch,var(--primary) 10%,var(--background))}.dash-state.warning{background:color-mix(in oklch,var(--chart-4) 12%,var(--background))}.dash-state.danger{color:var(--destructive);border-color:color-mix(in oklch,var(--destructive) 30%,var(--border))}.dash-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}.dash-form-grid .control{min-height:32px;padding:.35rem .5rem;font-size:.62rem}.dash-form-grid textarea.control{min-height:70px}.dash-form-grid .label,.dash-form-grid .choice{font-size:.6rem}.dash-form-grid input[type=range]{width:100%}.adapter-list{overflow:hidden;border:1px solid var(--border);border-radius:var(--radius)}.adapter-row{display:grid;grid-template-columns:1fr auto auto;gap:.4rem;align-items:center;padding:.45rem;border-bottom:1px solid var(--border);font-size:.6rem}.adapter-row:last-child{border-bottom:0}.adapter-row small{display:block;color:var(--muted-foreground)}.adapter-ok{padding:.1rem .3rem;border-radius:4px;background:color-mix(in oklch,var(--primary) 12%,var(--background));color:var(--primary);font-weight:700}.dash-second{grid-column:1/-1;display:grid;grid-template-columns:.78fr .9fr 1.05fr .48fr;gap:.65rem}.dash-tabs .tabs{margin-bottom:.5rem}.dash-tabs .tab{padding:.35rem .55rem;font-size:.6rem}.mini-alert{display:flex;justify-content:space-between;margin-top:.35rem;padding:.37rem .45rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.58rem}.mini-alert.good{color:var(--primary)}.mini-alert.warn{color:var(--chart-4)}.mini-alert.bad{color:var(--destructive)}.dash-table{width:100%;border-collapse:collapse;font-size:.56rem}.dash-table th,.dash-table td{padding:.36rem .3rem;text-align:left;border-bottom:1px solid var(--border)}.dash-table th{color:var(--muted-foreground)}.status-dot{display:inline-flex;align-items:center;gap:.2rem;padding:.08rem .28rem;border-radius:999px;background:var(--secondary);font-size:.52rem}.status-dot::before{content:"";width:4px;height:4px;border-radius:50%;background:var(--primary)}.mini-chart{display:flex;align-items:end;gap:.55rem;height:150px;padding:1rem .35rem .25rem;border-bottom:1px solid var(--border)}.mini-bar{position:relative;flex:1;background:var(--chart-1);border-radius:2px 2px 0 0}.mini-bar::after{content:"";position:absolute;left:55%;bottom:0;width:45%;height:72%;background:var(--chart-2);opacity:.5}.mini-bar:nth-child(1){height:48%}.mini-bar:nth-child(2){height:72%}.mini-bar:nth-child(3){height:94%}.mini-bar:nth-child(4){height:61%}.mini-bar:nth-child(5){height:58%}.mini-bar:nth-child(6){height:66%}.mini-chart-labels{display:flex;justify-content:space-between;color:var(--muted-foreground);font-size:.5rem}.dash-popover{margin-top:.55rem;padding:.7rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--popover);box-shadow:var(--shadow-lg);font-size:.6rem}.dash-popover p{color:var(--muted-foreground)}.dash-tokens{grid-column:1/-1}.token-strip{display:grid;grid-template-columns:1.3fr .8fr 1fr;gap:.75rem}.palette-strip,.radius-strip,.shadow-strip{display:flex;gap:.38rem}.palette-sample{flex:1;min-width:0}.palette-color{height:38px;border:1px solid var(--border);border-radius:var(--radius)}.palette-sample small,.radius-sample small,.shadow-sample small{display:block;margin-top:.2rem;color:var(--muted-foreground);font-size:.47rem;overflow:hidden}.radius-sample{flex:1;height:38px;border:1px solid var(--border);background:var(--background)}.shadow-sample{flex:1;height:38px;border-radius:var(--radius);background:var(--background)}.shadow-sample:nth-child(1){box-shadow:var(--shadow-sm)}.shadow-sample:nth-child(2){box-shadow:var(--shadow-md)}.shadow-sample:nth-child(3){box-shadow:var(--shadow-xl)}@media(max-width:1100px){.dashboard-grid{grid-template-columns:1fr 1fr}.dash-second{grid-template-columns:1fr 1fr}.adapter-status{grid-column:1/-1}.dash-tokens{grid-column:1/-1}}@media(max-width:720px){.dashboard-grid,.dash-second,.token-strip{grid-template-columns:1fr}.dash-actions{grid-template-columns:1fr}.dash-states{padding:0;border:0}}
.mini-chart::before{content:"1K";inset:.3rem auto auto .1rem;display:block;line-height:1}.mini-chart-labels{grid-template-columns:repeat(7,1fr);text-align:center}.mini-bar:nth-child(7){height:62%}
.specimen,.specimen button,.specimen input,.specimen textarea,.specimen select{font-family:var(--font-sans),sans-serif}.specimen{--status-success:oklch(.58 .17 145);--status-warning:oklch(.68 .16 76);--status-info:oklch(.58 .15 245);--status-destructive:var(--destructive);--status-success-surface:color-mix(in srgb,var(--status-success) 9%,var(--background));--status-warning-surface:color-mix(in srgb,var(--status-warning) 10%,var(--background));--status-info-surface:color-mix(in srgb,var(--status-info) 9%,var(--background));--status-destructive-surface:color-mix(in srgb,var(--status-destructive) 8%,var(--background))}.dashboard-overview{height:calc(100vh - 109px);min-height:0;margin:0 4px 4px;padding:1.8rem 1.25rem 1.25rem;background:var(--background);border-radius:8px;box-shadow:var(--shadow-sm);overflow:hidden;font-size:1rem}.dashboard-grid{grid-template-columns:49fr 31fr 20fr;gap:.55rem}.dashboard-grid>.dash-card:nth-child(-n+3){height:292px}.dash-card{padding:.68rem;border:1px solid var(--border);box-shadow:var(--shadow-xs)}.dash-second{grid-template-columns:25.9fr 28.7fr 27.3fr 15.7fr;gap:.55rem;height:298px;min-height:0}.dash-second>.dash-card{height:100%}.dash-tokens{height:168px;min-height:0;padding:.8rem}.dashboard-overview .dash-label,.dashboard-overview .dash-demo small,.dashboard-overview .label{font-size:.79rem}.dashboard-overview .button,.dashboard-overview .dash-button{min-height:35px;padding:.42rem .72rem;font-size:.76rem}.dashboard-overview .control,.dash-form-grid .control{min-height:35px;padding:.42rem .55rem;font-size:.75rem;background:var(--background);border-color:var(--input)}.dash-form-grid textarea.control{min-height:78px}.dash-state{min-height:36px;display:flex;align-items:center;padding:.45rem .55rem;font-size:.72rem}.dash-state.success,.mini-alert.good{color:var(--status-success);background:var(--status-success-surface)}.dash-state.warning,.mini-alert.warn{color:var(--status-warning);background:var(--status-warning-surface)}.dash-state.danger,.mini-alert.bad{color:var(--status-destructive);background:var(--status-destructive-surface)}.mini-alert:first-of-type{color:var(--status-info);background:var(--status-info-surface)}.mini-alert{min-height:38px;display:flex;align-items:center;justify-content:flex-start;gap:.4rem;padding:.5rem .58rem;border-color:var(--border);font-size:.72rem}.mini-alert:not(:first-of-type)::after{content:"×";margin-left:auto}.adapter-row{min-height:44px;padding:.5rem .55rem;font-size:.71rem}.adapter-row small{font-size:.57rem}.adapter-ok{min-width:28px;min-height:20px;display:grid;place-items:center;color:var(--status-success);background:var(--status-success-surface);border:1px solid color-mix(in srgb,var(--status-success) 25%,var(--border))}.adapter-row>span:last-child{display:grid;place-items:center;width:19px;height:19px;color:var(--status-success);border:1px solid var(--border);border-radius:50%}.dash-table{font-size:.71rem}.dash-table tr{height:36px}.dash-table th,.dash-table td{padding:.35rem .32rem}.compact-pages{display:flex;align-items:center;gap:.2rem;font-size:.62rem}.compact-pages button{width:25px;height:25px;padding:0;border:0;background:transparent;color:var(--foreground)}.dash-popover{position:relative;margin-top:.7rem;padding:.85rem;font-size:.68rem}.dash-popover::before{content:"";position:absolute;top:-6px;left:24px;width:10px;height:10px;transform:rotate(45deg);background:var(--popover);border-top:1px solid var(--border);border-left:1px solid var(--border)}.loading-spinner{width:12px;height:12px;margin-left:.35rem;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:spin .7s linear infinite}.mini-chart{padding-left:2rem;background:repeating-linear-gradient(to bottom,transparent 0,transparent calc(25% - 1px),color-mix(in srgb,var(--border) 75%,var(--foreground)) 25%)}.mini-chart::before{content:"1K\A 750\A 500\A 250\A 0";inset:.25rem auto auto .05rem;display:block;width:1.65rem;white-space:pre;text-align:right;line-height:37px;color:var(--foreground);font-size:.53rem}.mini-bar{background:linear-gradient(to right,var(--foreground) 0 44%,transparent 44% 100%)}.mini-bar::after{left:56%;width:44%;height:72%;background:var(--muted);opacity:1}.mini-chart::after{content:"■ Sessions   ▪ New users";color:var(--foreground)}.token-strip{grid-template-columns:1.55fr .85fr 1.15fr}.palette-strip,.radius-strip,.shadow-strip{align-items:flex-start}.palette-color{width:100%;height:42px}.palette-sample small{min-height:35px;font-size:.57rem;line-height:1.15}.radius-strip,.shadow-strip{padding-bottom:28px}.radius-sample,.shadow-sample{position:relative;height:42px}.radius-sample small,.shadow-sample small{position:absolute;top:46px;left:0;width:100%;white-space:normal}.token-value,.shadow-spec{display:block;margin-top:1px;color:var(--muted-foreground);font-family:var(--font-mono);font-size:.44rem;line-height:1.12}.shadow-sample:nth-child(4){box-shadow:var(--shadow-2xl)}.dashboard-overview .icon-svg{width:14px;height:14px;margin-right:.28rem}.dashboard-overview .switch{width:34px;height:18px;padding:2px}.dashboard-overview .switch::after{width:14px;height:14px}.dashboard-overview .switch[aria-checked=true]::after{transform:translateX(16px)}
.preview-note{color:var(--muted-foreground);font-size:.58rem;font-weight:400}.cc-tabs .preview-active{color:var(--foreground);border-color:var(--primary)}
.mini-chart{position:relative}.mini-chart::after{position:absolute;top:.2rem;right:.35rem;font-size:.5rem}.textarea-counter{display:block;margin:-.15rem 0 .25rem;text-align:right;color:var(--muted-foreground);font-size:.58rem}
.dashboard-overview{background:var(--card);color:var(--card-foreground)}.dash-card{background:var(--background);color:var(--foreground);border-color:var(--border)}.dashboard-overview .control,.dashboard-overview select,.dashboard-overview textarea{background:var(--background);color:var(--foreground);border-color:var(--input)}.dashboard-overview .button.secondary{background:var(--secondary);color:var(--secondary-foreground)}.dashboard-overview .button.outline{background:var(--background);color:var(--foreground);border-color:var(--input)}.palette-color{display:block;width:100%;height:42px;border:1px solid var(--border);border-radius:var(--radius)}.radius-sample,.shadow-sample{display:block;flex:1;min-width:0;height:42px;background:var(--background);border:1px solid var(--border)}.radius-sample small,.shadow-sample small{overflow:visible}.token-value,.shadow-spec{overflow-wrap:anywhere}.dashboard-overview input[type=checkbox],.dashboard-overview input[type=radio]{appearance:none;width:14px;height:14px;margin:0;border:1px solid var(--input);background:var(--background);accent-color:var(--primary)}.dashboard-overview input[type=checkbox]{border-radius:3px}.dashboard-overview input[type=radio]{border-radius:50%}.dashboard-overview input[type=checkbox]:checked{background:var(--primary);box-shadow:inset 0 0 0 3px var(--background)}.dashboard-overview input[type=radio]:checked{background:var(--primary);box-shadow:inset 0 0 0 3px var(--background)}.dashboard-overview input[type=range]{appearance:none;width:100%;height:16px;margin:0;background:transparent;accent-color:var(--primary)}.dashboard-overview input[type=range]::-webkit-slider-runnable-track{height:3px;border-radius:999px;background:linear-gradient(to right,var(--primary) 0 60%,var(--secondary) 60% 100%)}.dashboard-overview input[type=range]::-webkit-slider-thumb{appearance:none;width:10px;height:10px;margin-top:-3.5px;border:1px solid var(--background);border-radius:50%;background:var(--primary);box-shadow:0 0 0 1px var(--ring)}.dashboard-overview input[type=range]::-moz-range-track{height:3px;border-radius:999px;background:var(--secondary)}.dashboard-overview input[type=range]::-moz-range-progress{height:3px;border-radius:999px;background:var(--primary)}.dashboard-overview input[type=range]::-moz-range-thumb{width:10px;height:10px;border:1px solid var(--background);border-radius:50%;background:var(--primary)}.dashboard-overview .switch{background:var(--input)}.dashboard-overview .switch[aria-checked=true]{background:var(--primary)}.mini-chart{border-bottom-color:var(--border)}.token-strip{gap:.9rem}.palette-strip,.radius-strip,.shadow-strip{gap:.42rem}.dashboard-grid{row-gap:.55rem}
.shell-tranche{grid-column:1/-1;display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:.75rem}.shell-group-heading{grid-column:1/-1;display:flex;align-items:end;justify-content:space-between;gap:1rem;margin:.45rem 0 -.15rem;padding-top:.5rem;border-top:1px solid var(--border)}.shell-group-heading h2{margin:0;font-size:.9rem}.shell-group-heading p{margin:0;color:var(--muted-foreground);font-size:.63rem}.shell-span-12{grid-column:span 12}.shell-span-8{grid-column:span 8}.shell-span-7{grid-column:span 7}.shell-span-6{grid-column:span 6}.shell-span-5{grid-column:span 5}.shell-span-4{grid-column:span 4}.shell-card-title{display:flex;align-items:center;justify-content:space-between;gap:.5rem}.shell-card-title h3{margin:0}.dock-stage{position:relative;display:grid;place-items:end center;min-height:178px;padding:1rem;background:linear-gradient(145deg,var(--muted),var(--background));border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}.dock-context{position:absolute;top:1rem;right:1rem;width:142px;padding:.35rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-md);font-size:.6rem}.dock-context span{display:block;padding:.35rem;border-radius:calc(var(--radius)*.7)}.dock-context span:first-child{background:var(--accent);color:var(--accent-foreground)}.dock{position:relative;display:flex;align-items:end;gap:.35rem;padding:.45rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:calc(var(--radius)*1.25);box-shadow:var(--shadow-lg)}.dock-item{position:relative;display:grid;place-items:center;width:42px;height:42px;border:1px solid transparent;border-radius:var(--radius);background:var(--secondary);color:var(--secondary-foreground)}.dock-item.running::after,.dock-item.focused::after{content:"";position:absolute;bottom:-5px;width:14px;height:2px;border-radius:999px;background:var(--primary)}.dock-item.focused{background:var(--primary);color:var(--primary-foreground)}.dock-item.urgent{color:var(--destructive);border-color:var(--destructive);background:var(--status-destructive-surface)}.dock-item.hovered{background:var(--accent);color:var(--accent-foreground);transform:translateY(-5px)}.dock-tooltip{position:absolute;bottom:54px;padding:.25rem .4rem;white-space:nowrap;background:var(--foreground);color:var(--background);border-radius:var(--radius);font-size:.56rem}.dock-item.drag-target{border-style:dashed;border-color:var(--ring);box-shadow:0 0 0 2px color-mix(in srgb,var(--ring) 24%,transparent)}.dock-autohide{position:absolute;bottom:0;width:96px;height:3px;border-radius:999px 999px 0 0;background:var(--primary)}.state-legend{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.65rem;color:var(--muted-foreground);font-size:.58rem}.state-legend span{padding:.18rem .35rem;border:1px solid var(--border);border-radius:999px}.lock-preview{display:grid;grid-template-columns:1.05fr .95fr;gap:.75rem;min-height:310px;padding:1rem;background:linear-gradient(135deg,var(--sidebar),var(--background));border:1px solid var(--border);border-radius:var(--radius)}.lock-identity{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;color:var(--foreground)}.lock-clock{font-size:2.6rem;font-weight:700;line-height:1}.lock-date{margin-top:.3rem;color:var(--muted-foreground);font-size:.68rem}.user-avatar{display:grid;place-items:center;width:52px;height:52px;margin:1rem 0 .4rem;border-radius:50%;background:var(--primary);color:var(--primary-foreground)}.lock-auth{display:grid;align-content:center;gap:.5rem;padding:.8rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-lg)}.lock-auth .control{min-height:36px;font-size:.68rem}.lock-error{display:flex;align-items:center;gap:.35rem;color:var(--destructive);font-size:.62rem}.session-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.45rem}.session-action{display:flex;align-items:center;gap:.4rem;min-height:38px;padding:.45rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--background);color:var(--foreground);font-size:.62rem}.session-action.danger{color:var(--destructive);border-color:color-mix(in srgb,var(--destructive) 35%,var(--border))}.settings-window{display:grid;grid-template-columns:170px minmax(0,1fr);min-height:430px;border:1px solid var(--sidebar-border);border-radius:var(--radius);overflow:hidden}.settings-sidebar{padding:.75rem;background:var(--sidebar);color:var(--sidebar-foreground)}.settings-sidebar strong{display:block;margin-bottom:.6rem;font-size:.72rem}.settings-sidebar span{display:flex;align-items:center;gap:.4rem;margin:.18rem 0;padding:.42rem;border-radius:var(--radius);font-size:.62rem}.settings-sidebar .selected{background:var(--sidebar-primary);color:var(--sidebar-primary-foreground)}.settings-content{padding:.8rem;background:var(--background);color:var(--foreground)}.settings-search{margin-bottom:.65rem}.settings-search .control{min-height:34px;font-size:.65rem}.settings-panels{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}.setting-block{padding:.6rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--card-foreground);font-size:.63rem}.setting-row{display:grid;grid-template-columns:1fr auto;gap:.6rem;align-items:center;padding:.38rem 0;border-bottom:1px solid var(--border)}.setting-row:last-child{border-bottom:0}.setting-row small{display:block;color:var(--muted-foreground)}.setting-row .control{width:120px;min-height:30px;padding:.3rem .4rem;font-size:.58rem}.setting-row input[type=range]{width:120px;accent-color:var(--primary)}.setting-color{width:28px;height:28px;border:1px solid var(--border);border-radius:var(--radius);background:var(--primary)}.widget-layout-row{display:flex;gap:.3rem;margin-top:.45rem}.widget-layout-row span{flex:1;height:48px;border:1px dashed var(--ring);border-radius:var(--radius);background:var(--muted)}.plugin-grid{display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin-top:.45rem}.plugin-card{padding:.5rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--background)}.plugin-card strong,.plugin-card small{display:block}.plugin-card small{color:var(--muted-foreground)}.utility-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:.55rem}.wallpaper-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.35rem}.wallpaper-thumb{position:relative;min-height:76px;border:1px solid var(--border);border-radius:var(--radius);background:linear-gradient(135deg,var(--chart-1),var(--chart-3))}.wallpaper-thumb:nth-child(2){background:linear-gradient(145deg,var(--chart-2),var(--muted))}.wallpaper-thumb:nth-child(3){background:linear-gradient(145deg,var(--chart-4),var(--chart-5))}.wallpaper-thumb.selected{outline:2px solid var(--ring);outline-offset:1px}.wallpaper-thumb span{position:absolute;inset:auto .3rem .3rem;padding:.18rem .25rem;background:var(--popover);color:var(--popover-foreground);border-radius:calc(var(--radius)*.6);font-size:.52rem}.clipboard-list{display:grid;gap:.35rem}.clipboard-item{display:grid;grid-template-columns:24px 1fr auto;gap:.4rem;align-items:center;padding:.45rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--background);font-size:.6rem}.clipboard-item:first-child{background:var(--accent);color:var(--accent-foreground)}.capture-layout{display:grid;grid-template-columns:repeat(2,1fr);gap:.4rem}.capture-action{display:grid;place-items:center;gap:.2rem;min-height:64px;padding:.4rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--background);color:var(--foreground);font-size:.58rem}.output-list{display:grid;gap:.35rem;margin-top:.55rem}.output-row{display:grid;grid-template-columns:28px 1fr auto;gap:.45rem;align-items:center;padding:.42rem;border:1px solid var(--border);border-radius:var(--radius);font-size:.6rem}.output-row.current{border-color:var(--ring);background:var(--accent);color:var(--accent-foreground)}.widget-canvas{position:relative;display:grid;grid-template-columns:1fr 1.2fr 1fr;grid-template-rows:auto auto;gap:.55rem;min-height:390px;padding:1rem;background:linear-gradient(140deg,var(--muted),var(--background));border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}.desktop-widget{min-width:0;padding:.65rem;background:var(--popover);color:var(--popover-foreground);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-md);font-size:.62rem}.desktop-widget h4{margin:0 0 .4rem;font-size:.65rem}.widget-clock{grid-column:1;grid-row:1}.widget-clock strong{display:block;font-size:1.65rem}.widget-calendar{grid-column:1;grid-row:2}.calendar-days{display:grid;grid-template-columns:repeat(7,1fr);gap:.18rem;text-align:center;font-size:.5rem}.calendar-days span{padding:.2rem}.calendar-days .today{background:var(--primary);color:var(--primary-foreground);border-radius:50%}.widget-media{grid-column:2;grid-row:1}.widget-weather{grid-column:3;grid-row:1}.weather-temp{font-size:1.4rem;font-weight:700}.widget-volume{grid-column:2;grid-row:2}.widget-sysmon{grid-column:3;grid-row:2}.sysmon-bars{display:flex;align-items:end;gap:.2rem;height:54px}.sysmon-bars span{flex:1;background:var(--chart-1);border-radius:2px 2px 0 0}.sysmon-bars span:nth-child(1){height:42%}.sysmon-bars span:nth-child(2){height:78%;background:var(--chart-2)}.sysmon-bars span:nth-child(3){height:58%;background:var(--chart-3)}.sysmon-bars span:nth-child(4){height:88%;background:var(--chart-4)}.edit-frame{position:absolute;inset:92px 31% 126px 31%;border:2px solid var(--ring);border-radius:var(--radius);pointer-events:none}.edit-handle{position:absolute;width:9px;height:9px;background:var(--ring);border:2px solid var(--background);border-radius:50%}.edit-handle.nw{top:-5px;left:-5px}.edit-handle.ne{top:-5px;right:-5px}.edit-handle.sw{bottom:-5px;left:-5px}.edit-handle.se{right:-5px;bottom:-5px}.edit-label{position:absolute;top:-24px;left:0;padding:.2rem .35rem;background:var(--ring);color:var(--background);border-radius:var(--radius);font-size:.52rem}.niri-fixture{display:grid;grid-template-columns:1fr 1fr;gap:.65rem}.niri-window-map{position:relative;display:grid;grid-template-columns:1fr .65fr;grid-template-rows:1fr .7fr;gap:.4rem;min-height:190px;padding:.65rem;background:var(--muted);border:1px solid var(--border);border-radius:var(--radius)}.niri-window{padding:.45rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--card-foreground);font-size:.56rem}.niri-window.focused{grid-row:1/3;border-color:var(--ring);box-shadow:0 0 0 1px var(--ring)}.niri-owned-note{display:grid;align-content:center;gap:.5rem;padding:.8rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--status-info-surface);color:var(--status-info);font-size:.65rem}.niri-owned-note strong{font-size:.72rem}.niri-owned-note p{margin:0;color:var(--foreground)}@media(max-width:1100px){.shell-span-8,.shell-span-7,.shell-span-6,.shell-span-5,.shell-span-4{grid-column:span 12}.settings-panels,.utility-grid{grid-template-columns:1fr}.widget-canvas{grid-template-columns:1fr 1fr}.widget-clock,.widget-calendar,.widget-media,.widget-weather,.widget-volume,.widget-sysmon{grid-column:auto;grid-row:auto}.edit-frame{inset:86px 49% 125px 2%}}@media(max-width:700px){.shell-group-heading{align-items:flex-start;flex-direction:column}.lock-preview,.settings-window,.settings-panels,.niri-fixture,.utility-grid,.widget-canvas{grid-template-columns:1fr}.settings-sidebar{display:flex;gap:.25rem;overflow-x:auto}.settings-sidebar strong{display:none}.settings-sidebar span{flex:none}.wallpaper-grid{grid-template-columns:1fr}.edit-frame{display:none}}
@media(max-width:720px){.dashboard-grid,.dash-second,.token-strip{grid-template-columns:minmax(0,1fr)}.dashboard-grid>.dash-card:nth-child(-n+3){height:auto}.dashboard-head{align-items:stretch;flex-direction:column;gap:.75rem}.dashboard-head>*,.dash-card,.dash-actions>*,.dash-demo,.dash-form-grid>*{min-width:0}.dashboard-head>.dash-button{width:100%}.dash-actions{grid-template-columns:minmax(0,1fr)}.dash-button-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}.dash-button-row>.dash-demo,.dash-button-row>.button{width:100%}.dash-demo .dash-button{width:100%;white-space:normal}.dash-states{padding:0;border:0}.dash-form-grid{grid-template-columns:minmax(0,1fr)}.dash-second>.dash-card{overflow-x:auto}.dash-table{min-width:32rem}.metric-row{align-items:flex-start;flex-wrap:wrap}.compact-pages{max-width:100%;flex-wrap:wrap}.adapter-row{grid-template-columns:minmax(0,1fr) auto auto}.adapter-row strong,.adapter-row small,.metric-row span,.metric-row strong{overflow-wrap:anywhere}.shell-grid,.shell-lower{grid-template-columns:minmax(0,1fr)}.shell-card,.shell-card *{min-width:0}.noctalia-bar{grid-template-columns:minmax(0,1fr)}.notification>span:nth-child(2),.launcher-item>span:nth-child(2),.quick-tile>span:last-child{overflow-wrap:anywhere}.shell-overview .section-head{align-items:flex-start;flex-direction:column;gap:.75rem}}@media(max-width:380px){.dash-button-row{grid-template-columns:minmax(0,1fr)}}
html{overflow-x:hidden}
.section-nav{width:100%;max-width:100vw}
.gallery-shell,.gallery-main,.specimen-boundary,.specimen,.spec-section,.grid>*{min-width:0}
.specimen{max-width:100%;overflow-x:clip}
.dashboard-grid>.dash-card:nth-child(-n+3){height:auto;min-height:292px}
@media(max-width:1100px){.dash-actions{grid-template-columns:minmax(0,1fr)}.dash-button-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));width:100%}.dash-button-row>.dash-demo,.dash-button-row>.button,.dash-demo .dash-button{width:100%;min-width:0;white-space:normal}.dash-form-grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:720px){.dashboard-overview{min-height:0}.dashboard-grid,.dash-second{display:flex;flex-direction:column}.dashboard-grid>.dash-card:nth-child(-n+3){min-height:0}.dash-second>.dash-card{height:auto}}
@media(max-width:600px){.grid{grid-template-columns:minmax(0,1fr);max-width:100%}.table-wrap,.dash-second>.dash-card{width:100%;max-width:100%;overflow-x:auto}}
@media(prefers-reduced-motion:reduce){.dashboard-overview .loading-spinner{animation:none}}
/* SPECIMEN_CSS_END */
"""
def section_heading(identifier: str, title: str, description: str) -> str:
    return f'<div class="section-head"><h2 id="{identifier}-title">{title}</h2><p>{description}</p></div>'


def svg_icon(name: str) -> str:
    """Return one local, dependency-free line icon for static shell previews."""
    paths = {
        "wifi": '<path d="M2.5 6a8 8 0 0 1 11 0M4.7 8.3a4.8 4.8 0 0 1 6.6 0M7 10.6a1.5 1.5 0 0 1 2 0M8 13h.1"/>',
        "volume": '<path d="M3 6h2l3-2.5v9L5 10H3Z"/><path d="M10 6a3 3 0 0 1 0 4M12 4a5.5 5.5 0 0 1 0 8"/>',
        "battery": '<rect x="2" y="5" width="11" height="6" rx="1"/><path d="M14 7v2M4 7h5"/>',
        "plus": '<path d="M8 3v10M3 8h10"/>',
        "niri": '<path d="m8 2 5 6-5 6-5-6Z"/><path d="m5.5 8 2.5-3 2.5 3L8 11Z"/>',
        "home": '<path d="M3 9.5 8 4l5 5.5V14H9.7v-3.5H6.3V14H3Z"/>',
        "pointer": '<path d="M5 13 8 4l2 5 4 2-9 2Z"/>',
        "panel": '<rect x="2.5" y="3" width="11" height="10" rx="1.5"/><path d="M6 3v10M6 7h7"/>',
        "table": '<rect x="2.5" y="3" width="11" height="10" rx="1"/><path d="M2.5 7h11M6.5 3v10"/>',
        "list": '<path d="M5 4h8M5 8h8M5 12h8M2.5 4h.1M2.5 8h.1M2.5 12h.1"/>',
        "message": '<path d="M3 4.5h10v7H7l-3 2v-2H3Z"/>',
        "palette": '<path d="M8 2.5a5.5 5.5 0 1 0 0 11h1a1.4 1.4 0 0 0 .4-2.7l-.3-.1a1 1 0 0 1 .3-2H13A5.5 5.5 0 0 0 8 2.5Z"/><path d="M5 6h.1M7.5 4.5h.1M10.5 5.2h.1"/>',
        "upload": '<path d="M8 11V3M5 6l3-3 3 3M3 10v3h10v-3"/>',
        "diff": '<path d="M5 3v10M11 3v10M3 5l2-2 2 2M9 11l2 2 2-2"/>',
        "settings": '<circle cx="8" cy="8" r="2"/><path d="M8 2.5v1.3M8 12.2v1.3M2.5 8h1.3M12.2 8h1.3M4.1 4.1l.9.9M11 11l.9.9M11 5l.9-.9M4.1 11.9l.9-.9"/>',
        "info": '<circle cx="8" cy="8" r="6"/><path d="M8 7v4M8 4.5h.1"/>',
        "alert": '<path d="M8 2.5 14 13H2Z"/><path d="M8 6v3M8 11.5h.1"/>',
        "close": '<circle cx="8" cy="8" r="6"/><path d="m6 6 4 4M10 6l-4 4"/>',
        "first": '<path d="M5 3v10M12 4 8 8l4 4"/>',
        "prev": '<path d="m10 4-4 4 4 4"/>',
        "next": '<path d="m6 4 4 4-4 4"/>',
        "last": '<path d="M11 3v10M4 4l4 4-4 4"/>',
        "terminal": '<rect x="2" y="3" width="12" height="10" rx="2"/><path d="m5 6 2 2-2 2M9 10h2"/>',
        "window": '<rect x="2.5" y="3" width="11" height="10" rx="1.5"/><path d="M2.5 6h11"/>',
        "image": '<rect x="2.5" y="3" width="11" height="10" rx="1.5"/><path d="m4 11 3-3 2 2 1.5-1.5L13 11M5.5 6h.1"/>',
        "smile": '<circle cx="8" cy="8" r="5.5"/><path d="M6 6.5h.1M10 6.5h.1M5.5 9.5a3.5 3.5 0 0 0 5 0"/>',
        "bluetooth": '<path d="M6 3v10l5-4-5-6v10l5-6Z"/>',
        "moon": '<path d="M12.5 10.5A5.5 5.5 0 0 1 5.5 3.5a5 5 0 1 0 7 7Z"/>',
        "gauge": '<path d="M3 11a5.5 5.5 0 1 1 10 0M8 8l3-2"/>',
        "pause": '<path d="M6 4v8M10 4v8"/>',
        "check": '<path d="M3 8.5 6.5 12 13 5"/>',
        "download": '<path d="M8 3v7M5 7l3 3 3-3M3 13h10"/>',
        "music": '<path d="M6 12V5l6-1v7M4.5 13.5A1.5 1.5 0 1 0 6 12M10.5 12.5A1.5 1.5 0 1 0 12 11"/>',
        "sun": '<circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v1.3M8 13.2v1.3M1.5 8h1.3M13.2 8h1.3M3.4 3.4l.9.9M11.7 11.7l.9.9M11.7 4.3l.9-.9M3.4 12.6l.9-.9"/>',
        "pin": '<path d="m5 3 6 6M9.5 2.5l4 4-2 1-3-3ZM6.5 8.5 3 13"/>',
        "lock": '<rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2M8 10v1.5"/>',
        "user": '<circle cx="8" cy="5" r="2.5"/><path d="M3 14a5 5 0 0 1 10 0"/>',
        "logout": '<path d="M7 3H3v10h4M9 5l3 3-3 3M12 8H6"/>',
        "restart": '<path d="M12.5 5V2.5H10M12 4a5 5 0 1 0 1 5"/>',
        "power": '<path d="M8 2v6M4.3 4.3a5 5 0 1 0 7.4 0"/>',
        "folder": '<path d="M2.5 5h4l1-1.5h6V13h-11Z"/>',
        "copy": '<rect x="5" y="5" width="8" height="8" rx="1"/><path d="M3 10H2.5V2.5H10V3"/>',
        "camera": '<rect x="2" y="4.5" width="12" height="8.5" rx="1.5"/><path d="m5 4.5 1-2h4l1 2"/><circle cx="8" cy="8.5" r="2.3"/>',
        "monitor": '<rect x="2" y="3" width="12" height="9" rx="1"/><path d="M6 14h4M8 12v2"/>',
        "cloud": '<path d="M4.5 12.5h7a2.5 2.5 0 0 0 .2-5 4 4 0 0 0-7.5 1A2 2 0 0 0 4.5 12.5Z"/>',
        "calendar": '<rect x="2.5" y="3.5" width="11" height="10" rx="1.5"/><path d="M5 2v3M11 2v3M2.5 7h11"/>',
        "cpu": '<rect x="4.5" y="4.5" width="7" height="7" rx="1"/><path d="M6 1.5v3M10 1.5v3M6 11.5v3M10 11.5v3M1.5 6h3M11.5 6h3M1.5 10h3M11.5 10h3"/>',
        "grip": '<path d="M5 4h.1M8 4h.1M11 4h.1M5 8h.1M8 8h.1M11 8h.1M5 12h.1M8 12h.1M11 12h.1"/>',
        "play": '<path d="m6 4 6 4-6 4Z"/>',
        "microphone": '<rect x="6" y="2" width="4" height="8" rx="2"/><path d="M4 8a4 4 0 0 0 8 0M8 12v2M6 14h4"/>',
    }
    path = paths.get(name, paths["window"])
    return f'<svg class="icon-svg" viewBox="0 0 16 16" aria-hidden="true">{path}</svg>'


def shell_preview_card(title: str, body: str, span: int = 12) -> str:
    """Wrap one explicitly inert shell composition in the shared specimen card."""
    return (
        f'<article class="shell-card shell-span-{span}" data-preview="inert">'
        f'<div class="shell-card-title"><h3>{title}</h3>'
        '<small class="preview-note">inert preview</small></div>'
        f'{body}</article>'
    )


def shell_tranche_markup() -> str:
    """Render Noctalia tranche-two compositions from semantic specimen roles."""
    dock = f"""
      <div class="dock-stage" role="group" aria-label="Dock state specimen">
        <div class="dock-context" aria-label="Inert dock context menu"><span>New window</span><span>Pin to dock</span><span>Close</span></div>
        <div class="dock" aria-label="Pinned and running applications">
          <span class="dock-item" aria-label="Files, pinned">{svg_icon('folder')}</span>
          <span class="dock-item running" aria-label="Browser, running">{svg_icon('window')}</span>
          <span class="dock-item focused" aria-label="Terminal, focused">{svg_icon('terminal')}</span>
          <span class="dock-item urgent" aria-label="Messages, urgent">{svg_icon('message')}</span>
          <span class="dock-item hovered" aria-label="Settings, hover preview">{svg_icon('settings')}<span class="dock-tooltip">Settings</span></span>
          <span class="dock-item drag-target" aria-label="Drag target preview">{svg_icon('plus')}</span>
        </div>
        <span class="dock-autohide" role="img" aria-label="Auto-hide edge indicator"></span>
      </div>
      <div class="state-legend"><span>Pinned</span><span>Running</span><span>Focused</span><span>Urgent</span><span>Hover + tooltip</span><span>Context menu</span><span>Drag target</span><span>Auto-hide edge</span></div>"""
    lock = f"""
      <div class="lock-preview" role="group" aria-label="Lock and session state specimen">
        <div class="lock-identity"><time class="lock-clock" datetime="10:24">10:24</time><span class="lock-date">Friday, August 29</span><span class="user-avatar">{svg_icon('user')}</span><strong>Andy</strong><span class="subtle">eDP-1 · locked</span></div>
        <div class="lock-auth"><strong>{svg_icon('lock')} Unlock session</strong><label class="label" for="shell-password">Password</label><input class="control" id="shell-password" type="password" value="incorrect" aria-invalid="true" aria-describedby="shell-password-error" disabled><span class="lock-error" id="shell-password-error">{svg_icon('alert')} Password was not accepted.</span><button class="button" type="button" disabled>Log in</button><div class="session-grid"><button class="session-action" type="button" disabled>{svg_icon('moon')} Suspend</button><button class="session-action" type="button" disabled>{svg_icon('logout')} Log out</button><button class="session-action" type="button" disabled>{svg_icon('restart')} Reboot</button><button class="session-action danger" type="button" disabled>{svg_icon('power')} Shut down</button></div></div>
      </div>"""
    settings = f"""
      <div class="settings-window" role="group" aria-label="Settings window specimen">
        <aside class="settings-sidebar"><strong>Noctalia settings</strong><span class="selected">{svg_icon('panel')} Appearance</span><span>{svg_icon('settings')} General</span><span>{svg_icon('monitor')} Outputs</span><span>{svg_icon('gauge')} Widgets</span><span>{svg_icon('download')} Plugins</span></aside>
        <div class="settings-content"><div class="settings-search"><label class="sr-only" for="settings-search">Search settings</label><input class="control" id="settings-search" type="search" placeholder="Search settings…" disabled></div><div class="settings-panels">
          <section class="setting-block"><strong>Shell appearance</strong><div class="setting-row"><span>Blur panels<small>Compositor-supported surfaces</small></span><button class="switch" type="button" role="switch" aria-checked="true" aria-label="Blur panels" disabled></button></div><div class="setting-row"><label for="shell-opacity">Panel opacity<small>90 percent</small></label><input id="shell-opacity" type="range" value="90" disabled></div><div class="setting-row"><label for="shell-density">Density</label><select class="control" id="shell-density" disabled><option>Comfortable</option></select></div><div class="setting-row"><span>Accent token<small>Selected preset primary</small></span><span class="setting-color" aria-label="Primary token swatch"></span></div><div class="setting-row"><span>Wallpaper folder<small>Local files only</small></span><button class="button outline" type="button" disabled>{svg_icon('folder')} Choose</button></div></section>
          <section class="setting-block"><strong>Widget editor</strong><div class="widget-layout-row" aria-label="Inert widget layout"><span></span><span></span><span></span></div><small class="subtle">Drag regions, snapping, and layer order preview.</small><div class="plugin-grid"><div class="plugin-card"><strong>Weather</strong><small>Built in · enabled</small></div><div class="plugin-card"><strong>Visualiser</strong><small>Plugin · available</small></div><div class="plugin-card"><strong>Screen time</strong><small>Built in · enabled</small></div><div class="plugin-card"><strong>Custom button</strong><small>Template · local</small></div></div></section>
        </div></div>
      </div>"""
    utilities = f"""
      <div class="utility-grid">
        <section><h4>Wallpaper picker</h4><div class="wallpaper-grid" aria-label="Local wallpaper choices"><div class="wallpaper-thumb selected"><span>Current</span></div><div class="wallpaper-thumb"><span>Output 2</span></div><div class="wallpaper-thumb"><span>Span</span></div></div><div class="output-list"><div class="output-row current"><span>{svg_icon('monitor')}</span><span><strong>eDP-1</strong><br><small>2560 × 1600 · focused</small></span><span>1×</span></div><div class="output-row"><span>{svg_icon('monitor')}</span><span><strong>DP-2</strong><br><small>1920 × 1080 · right</small></span><span>1×</span></div></div></section>
        <section><h4>Clipboard history</h4><div class="clipboard-list" aria-label="Clipboard preview"><div class="clipboard-item"><span>{svg_icon('copy')}</span><span>forge.web_mode_tokens()</span><small>Now</small></div><div class="clipboard-item"><span>{svg_icon('image')}</span><span>shell-reference.png</span><small>4m</small></div><div class="clipboard-item"><span>{svg_icon('terminal')}</span><span>python3 gallery.py</span><small>8m</small></div></div></section>
      </div>"""
    capture = f"""
      <div class="capture-layout" aria-label="Screenshot utility preview"><button class="capture-action" type="button" disabled>{svg_icon('camera')}<span>Selection</span></button><button class="capture-action" type="button" disabled>{svg_icon('window')}<span>Window</span></button><button class="capture-action" type="button" disabled>{svg_icon('monitor')}<span>Output</span></button><button class="capture-action" type="button" disabled>{svg_icon('image')}<span>All outputs</span></button></div><div class="metric-row"><span>Delay</span><strong>3 seconds</strong></div><div class="metric-row"><span>Save to</span><strong>Pictures/Screenshots</strong></div>"""
    widgets = f"""
      <div class="widget-canvas" role="group" aria-label="Desktop widget canvas and edit state specimen">
        <section class="desktop-widget widget-clock"><h4>Clock</h4><strong>10:24</strong><span class="subtle">Friday · August 29</span></section>
        <section class="desktop-widget widget-calendar"><h4>{svg_icon('calendar')} August</h4><div class="calendar-days"><span>25</span><span>26</span><span>27</span><span>28</span><span class="today">29</span><span>30</span><span>31</span></div></section>
        <section class="desktop-widget widget-media"><h4>Media</h4><div class="media-row"><span class="album"></span><span><strong>Quiet Machines</strong><br><small>Shell Radio</small></span><span>{svg_icon('play')}</span></div></section>
        <section class="desktop-widget widget-weather"><h4>{svg_icon('cloud')} Weather</h4><span class="weather-temp">68°</span><div class="subtle">Clear · 72° / 54°</div></section>
        <section class="desktop-widget widget-volume"><h4>{svg_icon('volume')} Volume</h4><div class="osd-meter"><span style="width:68%"></span></div><div class="metric-row"><span>Speakers</span><strong>68%</strong></div></section>
        <section class="desktop-widget widget-sysmon"><h4>{svg_icon('cpu')} System monitor</h4><div class="sysmon-bars" role="img" aria-label="CPU history: 42, 78, 58, and 88 percent"><span></span><span></span><span></span><span></span></div></section>
        <div class="edit-frame" role="group" aria-label="Selected widget edit frame"><span class="edit-label">{svg_icon('grip')} drag · resize</span><span class="edit-handle nw"></span><span class="edit-handle ne"></span><span class="edit-handle sw"></span><span class="edit-handle se"></span></div>
      </div>"""
    niri = f"""
      <div class="niri-fixture"><div class="niri-window-map" role="img" aria-label="Niri compositor integration fixture: focused tiled window, floating window, and dynamic workspace 3"><div class="niri-window focused">Focused tiled window<br><small>Border + shadow consume theme-adjacent Niri settings</small></div><div class="niri-window">Floating window</div><div class="niri-window">Dynamic workspace 3</div></div><aside class="niri-owned-note"><strong>{svg_icon('niri')} Compositor-owned fixture</strong><p>Niri owns overview, workspace animation, tiling, focus, window borders, and window management. Theme Forge previews their integration boundary; it does not generate them as Noctalia widgets.</p><span>Top-layer bar · dynamic workspaces · trailing empty workspace</span></aside></div>"""
    heading = (
        '<div class="shell-group-heading"><div><h2>Complete shell surfaces</h2>'
        '<p>Regenerable Noctalia compositions plus an explicit Niri-owned boundary.</p></div>'
        '<span class="shell-badge">semantic tokens · static fixtures</span></div>'
    )
    return (
        f'<div class="shell-tranche">{heading}'
        f'{shell_preview_card("Dock states", dock, 12)}'
        f'{shell_preview_card("Lock screen &amp; session", lock, 5)}'
        f'{shell_preview_card("Settings", settings, 7)}'
        f'{shell_preview_card("Wallpaper, clipboard &amp; outputs", utilities, 8)}'
        f'{shell_preview_card("Screenshot controls", capture, 4)}'
        f'{shell_preview_card("Desktop widgets &amp; edit mode", widgets, 8)}'
        f'{shell_preview_card("Niri integration", niri, 4)}</div>'
    )


def dashboard_token_inventory(default: dict[str, Any]) -> str:
    """Render compact diagnostics from canonical tokens plus documented status extensions."""
    light = default["diagnostics"]["light"]
    roles = (
        ("Background", "background", "var(--background)"),
        ("Muted", "muted", "var(--muted)"),
        ("Border", "border", "var(--border)"),
        ("Foreground", "foreground", "var(--foreground)"),
        ("Primary", "primary", "var(--primary)"),
        ("Success", None, "var(--status-success)"),
        ("Warning", None, "var(--status-warning)"),
        ("Destructive", "destructive", "var(--destructive)"),
    )
    swatches = []
    for label, token, background in roles:
        if token:
            value = str(light.get(token, "not set"))
            suffix = ""
        elif label == "Success":
            value, suffix = "#1D9330", "<br>extension"
        else:
            value, suffix = "#CA8A00", "<br>extension"
        swatches.append(
            f'<span class="palette-sample"><span class="palette-color" style="background:{background}"></span>'
            f'<small>{label}<span class="token-value"'
            f'{f" data-token-name={html.escape(token, quote=True)!r}" if token else ""}>'
            f'{html.escape(value)}{suffix}</span></small></span>'
        )
    radii = "".join(
        f'<span class="radius-sample" style="border-radius:{pixels}px"><small>{index} · {pixels}px</small></span>'
        for index, pixels in enumerate((2, 4, 6, 8, 12, 16, 24))
    )
    shadows = "".join(
        f'<span class="shadow-sample"><small>{size}<span class="shadow-spec">{spec}</span></small></span>'
        for size, spec in (("sm", "0 1px 2px"), ("md", "0 4px 6px"), ("lg", "0 10px 15px"), ("xl", "0 20px 25px"))
    )
    return (
        '<div class="token-strip"><div><span class="dash-label">Color palette</span>'
        f'<div class="palette-strip">{"".join(swatches)}</div></div>'
        f'<div><span class="dash-label">Radius scale</span><div class="radius-strip">{radii}</div></div>'
        f'<div><span class="dash-label">Shadows</span><div class="shadow-strip">{shadows}</div></div></div>'
    )


def specimen_markup(default: dict[str, Any]) -> str:
    swatches = "".join(
        f'<div class="token"><span class="swatch" style="background:var(--{token})"></span><code>--{token}</code></div>'
        for token in SEMANTIC_TOKENS
    )
    return f"""
<div class="specimen" id="specimen" data-theme="light" style="{html.escape(declarations(default['modes']['light']), quote=True)}">
  <section class="spec-section dashboard-overview" id="overview" aria-labelledby="overview-title">
    <div class="dashboard-head"><div><h1 id="overview-title">Interface preview</h1><p>Live preview of the <span data-theme-title>{html.escape(str(default['title']))}</span> theme across core shadcn components. <span class="sr-only" data-theme-description>{html.escape(str(default['description']))}</span></p></div><button class="button outline dash-button">&lt;/&gt;&nbsp; View code⌄</button></div>
    <div class="dashboard-grid">
      <article class="dash-card"><h2>Actions</h2><div class="dash-actions"><div><h4>Buttons</h4><div class="dash-button-row"><span class="dash-demo"><small>Default</small><button class="button dash-button">Primary</button></span><span class="dash-demo"><small>Hover</small><button class="button dash-button demo-hover">Primary</button></span><span class="dash-demo"><small>Focused</small><button class="button dash-button" style="outline:2px solid var(--ring);outline-offset:2px">Primary</button></span><span class="dash-demo"><small>Pressed</small><button class="button dash-button demo-active">Primary</button></span><span class="dash-demo"><small>Disabled</small><button class="button dash-button" disabled>Primary</button></span><span class="dash-demo"><small>Loading</small><button class="button dash-button" aria-busy="true">Primary<span class="loading-spinner" aria-hidden="true"></span></button></span></div><h4>Variants</h4><div class="dash-button-row"><button class="button secondary dash-button">Secondary</button><button class="button outline dash-button">Outline</button><button class="button ghost dash-button">Ghost</button><button class="button link dash-button">Link</button></div><h4>Sizes</h4><div class="dash-button-row"><button class="button outline dash-button">Small</button><button class="button dash-button">Default</button><button class="button outline">Large</button></div></div><div class="dash-states"><h4>States</h4><div class="dash-state success">{svg_icon('check')} Success</div><div class="dash-state warning">{svg_icon('alert')} Warning</div><div class="dash-state danger">{svg_icon('close')} Destructive</div><div class="dash-state">{svg_icon('close')} Disabled</div></div></div></article>
      <article class="dash-card"><h2>Forms</h2><div class="dash-form-grid"><div><label class="label" for="dash-input">Input</label><input class="control" id="dash-input" placeholder="Type something…"><label class="label" for="dash-select">Select</label><select class="control" id="dash-select"><option>Select an option</option></select><label class="choice"><input type="checkbox" checked> Accept terms and conditions</label><div><span class="dash-label">Radio group</span><label class="choice"><input type="radio" name="dash-radio" checked> Option one</label><label class="choice"><input type="radio" name="dash-radio"> Option two</label></div></div><div><label class="label" for="dash-textarea">Textarea</label><textarea class="control" id="dash-textarea" placeholder="Enter details…"></textarea><span class="textarea-counter">0 / 200</span><span class="dash-label">Switch</span><button class="switch" type="button" role="switch" aria-checked="true" aria-label="Enable preview"></button><div class="metric-row"><span>Range</span><strong>60%</strong></div><input type="range" value="60" aria-label="Range"></div></div></article>
      <article class="dash-card adapter-status" data-preview="inert"><h2>Adapter list specimen</h2><p class="dash-label">Inert rows for comparing compact status treatments.</p><div class="adapter-list"><div class="adapter-row"><span><strong>GTK adapter</strong><small>Specimen label</small></span><span class="adapter-ok">Sample</span><span>{svg_icon('check')}</span></div><div class="adapter-row"><span><strong>Terminal adapter</strong><small>Specimen label</small></span><span class="adapter-ok">Sample</span><span>{svg_icon('check')}</span></div><div class="adapter-row"><span><strong>Bar adapter</strong><small>Specimen label</small></span><span class="adapter-ok">Sample</span><span>{svg_icon('check')}</span></div></div><div class="metric-row"><span>Diagnostic type</span><strong>Inert specimen</strong></div><button class="button outline dash-button" style="width:100%;margin-top:.4rem" disabled>Regenerate specimen</button></article>
      <div class="dash-second"><article class="dash-card dash-tabs"><h3>Tabs</h3><div class="tabs" role="tablist" aria-label="Dashboard tabs"><button class="tab" id="dash-tab-overview" role="tab" aria-selected="true" aria-controls="dash-panel-overview" tabindex="0">Overview</button><button class="tab" id="dash-tab-analytics" role="tab" aria-selected="false" aria-controls="dash-panel-analytics" tabindex="-1">Analytics</button><button class="tab" id="dash-tab-reports" role="tab" aria-selected="false" aria-controls="dash-panel-reports" tabindex="-1">Reports</button></div><div id="dash-panel-overview" role="tabpanel" aria-labelledby="dash-tab-overview"><p class="dash-label">Tabs organize content into related sections.</p><div class="mini-alert">{svg_icon('info')} This is an informational alert.</div><div class="mini-alert good">{svg_icon('check')} Your changes have been saved.</div><div class="mini-alert warn">{svg_icon('alert')} Please review before continuing.</div><div class="mini-alert bad">{svg_icon('close')} This action cannot be undone.</div></div><div id="dash-panel-analytics" role="tabpanel" aria-labelledby="dash-tab-analytics" hidden>Analytics view</div><div id="dash-panel-reports" role="tabpanel" aria-labelledby="dash-tab-reports" hidden>Reports view</div></article><article class="dash-card"><h3>Table</h3><table class="dash-table"><thead><tr><th>Name</th><th>Role</th><th>Status</th><th>Updated</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody><tr><td>Sofia Davis</td><td>Admin</td><td><span class="status-dot">Active</span></td><td>May 12</td><td><button class="table-action" aria-label="Actions for row">•••</button></td></tr><tr><td>Liam Johnson</td><td>Editor</td><td><span class="status-dot">Active</span></td><td>May 11</td><td><button class="table-action" aria-label="Actions for row">•••</button></td></tr><tr><td>Noah Williams</td><td>Viewer</td><td><span class="status-dot">Inactive</span></td><td>May 10</td><td><button class="table-action" aria-label="Actions for row">•••</button></td></tr><tr><td>Emma Brown</td><td>Editor</td><td><span class="status-dot">Pending</span></td><td>May 9</td><td><button class="table-action" aria-label="Actions for row">•••</button></td></tr><tr><td>Olivia Miller</td><td>Admin</td><td><span class="status-dot">Suspended</span></td><td>May 8</td><td><button class="table-action" aria-label="Actions for row">•••</button></td></tr></tbody></table><div class="metric-row"><span>Rows per page &nbsp;5⌄</span><span class="compact-pages"><span>1–5 of 23</span><button aria-label="First page">{svg_icon('first')}</button><button aria-label="Previous page">{svg_icon('prev')}</button><button aria-label="Next page">{svg_icon('next')}</button><button aria-label="Last page">{svg_icon('last')}</button></span></div></article><article class="dash-card"><h3>Chart <span class="badge" style="float:right">Last 7 days⌄</span></h3><div class="mini-chart" role="img" aria-label="Session and new user totals over seven days"><span class="mini-bar"></span><span class="mini-bar"></span><span class="mini-bar"></span><span class="mini-bar"></span><span class="mini-bar"></span><span class="mini-bar"></span><span class="mini-bar"></span></div><div class="mini-chart-labels"><span>May 6</span><span>May 7</span><span>May 8</span><span>May 9</span><span>May 10</span><span>May 11</span><span>May 12</span></div><p class="dash-label">Showing total sessions and new users.</p></article><article class="dash-card"><h3>Overlay preview</h3><button class="button dash-button">Open dialog</button><h4>Popover preview</h4><button class="button outline dash-button">Open popover</button><div class="dash-popover"><strong>Popover content</strong><p>This is a popover with helpful contextual information.</p><button class="button outline dash-button">Got it</button></div></article></div>
      <article class="dash-card dash-tokens"><h3>Tokens</h3>{dashboard_token_inventory(default)}</article>
    </div>
  </section>
  <section class="spec-section shell-overview" id="shell" aria-labelledby="shell-title">
    <div class="section-head"><div><h1 id="shell-title">Noctalia shell preview</h1><p>Live <span data-theme-title>{html.escape(str(default['title']))}</span> theme across Niri-aware shell surfaces. <span data-theme-description>{html.escape(str(default['description']))}</span></p></div><span class="shell-badge">{svg_icon('niri')} Niri · eDP-1</span></div>
    <div class="shell-grid">
      <section class="noctalia-bar" aria-label="Niri-aware top bar specimen"><div class="workspace-list" aria-label="Workspaces"><button class="workspace" aria-label="Workspace 1" disabled>1</button><button class="workspace" aria-current="true" aria-label="Workspace 2, current" disabled>2</button><button class="workspace" aria-label="Workspace 3" disabled>3</button><button class="workspace" aria-label="Empty trailing workspace" disabled>{svg_icon('plus')}</button></div><div class="active-window">Theme Forge — Noctalia shell assets</div><div class="system-widgets"><span class="system-pill">{svg_icon('wifi')} Wi-Fi</span><span class="system-pill">{svg_icon('volume')} 68%</span><span class="system-pill">{svg_icon('battery')} 72%</span><time class="system-pill" datetime="10:24">10:24</time></div></section>
      <article class="shell-card"><h3>Launcher <small class="preview-note">inert preview</small></h3><label class="sr-only" for="launcher-search">Search applications</label><div class="launcher-search"><input class="control" id="launcher-search" type="search" placeholder="Search apps, windows, or commands…" disabled></div><div class="launcher-results" aria-label="Launcher results" data-preview="inert"><div class="launcher-item"><span class="app-icon">{svg_icon('terminal')}</span><span><strong>Terminal</strong><br><span class="subtle">Open a command session</span></span><span class="key">Enter</span></div><div class="launcher-item"><span class="app-icon">{svg_icon('window')}</span><span><strong>Windows</strong><br><span class="subtle">Switch Niri window</span></span><span class="key">2</span></div><div class="launcher-item"><span class="app-icon">{svg_icon('image')}</span><span><strong>Wallpaper</strong><br><span class="subtle">Browse local library</span></span><span class="key">3</span></div><div class="launcher-item"><span class="app-icon">{svg_icon('smile')}</span><span><strong>Emoji</strong><br><span class="subtle">Search and copy</span></span><span class="key">4</span></div></div></article>
      <article class="shell-card"><h3>Control Center <small class="preview-note">inert preview</small></h3><div class="cc-tabs" aria-label="Inert Control Center preview"><button type="button" class="preview-active" disabled>Home</button><button type="button" disabled>Audio</button><button type="button" disabled>Network</button><button type="button" disabled>Power</button></div><div class="quick-grid"><button class="quick-tile" disabled aria-pressed="true"><span>{svg_icon('wifi')}</span><span><strong>Wi-Fi</strong><span>Forge Lab</span></span></button><button class="quick-tile" disabled aria-pressed="true"><span>{svg_icon('bluetooth')}</span><span><strong>Bluetooth</strong><span>2 devices</span></span></button><button class="quick-tile" disabled aria-pressed="false"><span>{svg_icon('moon')}</span><span><strong>Night light</strong><span>Off</span></span></button><button class="quick-tile" disabled aria-pressed="true"><span>{svg_icon('gauge')}</span><span><strong>Performance</strong><span>Balanced</span></span></button></div><div class="media-row"><span class="album" aria-hidden="true"></span><span><strong>Quiet Machines</strong><br><span class="subtle">Shell Radio</span></span><button class="button icon ghost" aria-label="Pause media" disabled>{svg_icon('pause')}</button></div></article>
      <article class="shell-card notifications"><h3>Notifications</h3><div class="notification-stack"><div class="notification"><span class="notif-dot">{svg_icon('check')}</span><span><strong>Theme applied</strong><p>Theme assets are ready.</p></span><time datetime="PT1M">1m</time></div><div class="notification"><span class="notif-dot">{svg_icon('download')}</span><span><strong>Update available</strong><p>3 packages can be updated.</p></span><time datetime="PT8M">8m</time></div><div class="notification"><span class="notif-dot">{svg_icon('music')}</span><span><strong>Now playing</strong><p>Quiet Machines</p></span><time>Now</time></div></div><h4>On-screen display</h4><div class="osd-stack"><div class="osd"><span>{svg_icon('volume')}</span><span class="osd-meter"><span></span></span><strong>46%</strong></div><div class="osd"><span>{svg_icon('sun')}</span><span class="osd-meter"><span></span></span><strong>72%</strong></div></div></article>
      <div class="shell-lower"><article class="shell-card"><h3>Audio output</h3><div class="metric-row"><span>Built-in speakers</span><strong>68%</strong></div><input type="range" min="0" max="100" value="68" aria-label="Output volume" disabled></article><article class="shell-card"><h3>Niri workspace state</h3><div class="metric-row"><span>Dynamic workspaces</span><strong>3 + empty</strong></div><div class="metric-row"><span>Focused output</span><strong>eDP-1</strong></div></article><article class="shell-card"><h3>Privacy &amp; session</h3><div class="row"><span class="badge primary">Microphone clear</span><button class="button outline" disabled>Session menu</button></div></article></div>
      {shell_tranche_markup()}
    </div>
  </section>
  <section class="spec-section" id="actions" aria-labelledby="actions-title">{section_heading('actions','Actions','Button variants and persistent interaction-state samples.')}
    <div class="grid"><article class="panel stack"><h3>Variants</h3><div class="row"><button class="button">Primary</button><button class="button secondary">Secondary</button><button class="button outline">Outline</button><button class="button ghost">Ghost</button><button class="button destructive">Delete</button><button class="button link">Learn more</button><button class="button icon" aria-label="Add item">+</button></div><div class="row" role="group" aria-label="Segmented view"><button class="button secondary" aria-pressed="true">Canvas</button><button class="button outline" aria-pressed="false">Tokens</button><button class="button outline" aria-pressed="false">Code</button></div><div class="row" role="group" aria-label="Split export action"><button class="button">Export</button><button class="button icon" aria-label="Choose export format">⌄</button></div></article><article class="panel stack"><h3>States</h3><div class="row"><span class="stack"><span class="state-label">hover</span><button class="button demo-hover">Preview</button></span><span class="stack"><span class="state-label">focus</span><button class="button outline" autofocus>Focused</button></span><span class="stack"><span class="state-label">active</span><button class="button demo-active">Pressed</button></span><span class="stack"><span class="state-label">loading</span><button class="button" aria-busy="true"><span class="spinner" aria-hidden="true"></span>Saving</button></span><span class="stack"><span class="state-label">disabled</span><button class="button" disabled>Disabled</button></span></div></article></div>
  </section>
  <section class="spec-section" id="forms" aria-labelledby="forms-title">{section_heading('forms','Forms','Inputs, selection controls, validation, and help states.')}
    <div class="grid"><form class="panel stack" onsubmit="return false"><div class="field"><label class="label" for="project-name">Project name</label><input class="control" id="project-name" value="Desktop retheme"><span class="subtle">Shown in generated asset metadata.</span></div><div class="field"><label class="label" for="password">Signing password</label><input class="control" id="password" type="password" value="theme-forge" aria-describedby="password-help"><span class="subtle" id="password-help">Stored only for this local specimen session.</span></div><div class="field"><label class="label" for="search">Search assets</label><input class="control" id="search" type="search" placeholder="Type a component name"></div><div class="field"><label class="label" for="notes">Review notes</label><textarea class="control" id="notes">Check focus and destructive states.</textarea></div><div class="field"><label class="label" for="target">Target adapter</label><select class="control" id="target"><option>GTK 4</option><option>Waybar</option><option>Kitty</option></select></div></form><article class="panel stack"><h3>Selection</h3><label class="choice"><input type="checkbox" checked> Include terminal assets</label><label class="choice"><input type="radio" name="density" checked> Comfortable density</label><label class="choice"><input type="radio" name="density"> Dense layout</label><div class="choice"><button class="switch" type="button" role="switch" aria-checked="true" aria-label="Enable live preview"></button><span>Live preview</span></div><label class="label" for="scale">Interface scale</label><input id="scale" type="range" min="0" max="100" value="68"></article><article class="panel stack"><h3>Validation</h3><div class="field"><label class="label" for="slug">Asset slug</label><input class="control" id="slug" value="Theme Asset" aria-invalid="true" aria-describedby="slug-error"><span class="error" id="slug-error">Use lowercase letters and hyphens only.</span></div><div class="field"><label class="label" for="readonly">Generated path</label><input class="control" id="readonly" value="out/themes/current" readonly></div><div class="field"><label class="label" for="disabled-input">Remote source</label><input class="control" id="disabled-input" value="Unavailable offline" disabled></div></article></div>
  </section>
  <section class="spec-section" id="overlays" aria-labelledby="overlays-title">{section_heading('overlays','Overlays','Keyboard-operable dialog, menu, tooltip, and toast surfaces.')}
    <div class="grid"><article class="panel stack"><h3>Dialog</h3><button class="button" id="dialog-open" aria-haspopup="dialog">Review export</button><dialog class="dialog" id="review-dialog" aria-labelledby="dialog-title"><div class="dialog-body stack"><h3 id="dialog-title">Export native assets?</h3><p class="subtle">This specimen demonstrates initial focus, Escape dismissal, and focus return.</p><div class="row"><button class="button" id="dialog-confirm">Export assets</button><button class="button outline" id="dialog-close">Cancel</button></div></div></dialog></article><article class="panel stack"><h3>Menu &amp; tooltip</h3><div class="row"><div class="menu-wrap"><button class="button outline" id="menu-trigger" aria-haspopup="menu" aria-expanded="false">Asset menu</button><div class="menu" id="asset-menu" role="menu" hidden><button role="menuitem">Duplicate preset</button><button role="menuitem">Copy token map</button><button role="menuitem">Open preview</button></div></div><span class="tooltip-wrap"><button class="button icon" aria-describedby="tip">?</button><span class="tooltip" role="tooltip" id="tip">Local semantic token help</span></span></div></article><article class="panel stack"><h3>Popover &amp; sheet</h3><div class="popover-wrap"><button class="button outline" id="popover-trigger" aria-expanded="false" aria-controls="token-popover">Token details</button><div class="popover-panel" id="token-popover" hidden><strong>Primary foreground</strong><p class="subtle">Paired semantic text for primary actions.</p></div></div><button class="button outline" id="sheet-open" aria-expanded="false" aria-controls="asset-sheet">Open asset sheet</button><aside class="sheet stack" id="asset-sheet" aria-labelledby="sheet-title" hidden><h3 id="sheet-title">Generated assets</h3><p class="subtle">Inspect native targets without leaving the current section.</p><button class="button outline" id="sheet-close">Close sheet</button></aside></article><article class="panel stack"><h3>Toast</h3><div class="toast" role="status"><span aria-hidden="true">✓</span><div><strong>Assets generated</strong><div class="subtle">Six adapters are ready for review.</div></div></div></article></div>
  </section>
  <section class="spec-section" id="data" aria-labelledby="data-title">{section_heading('data','Data','Cards, table density, progress, loading, and token-driven charts.')}
    <div class="grid"><article class="card" data-preview="inert"><span class="subtle">Progress specimen</span><div class="stat">68%</div><div class="progress" role="progressbar" aria-label="Inert progress specimen" aria-valuenow="68" aria-valuemin="0" aria-valuemax="100"><span></span></div><div class="separator" role="separator"></div><details><summary>Specimen details</summary><p class="subtle">Example disclosure copy; no build result is asserted.</p></details></article><article class="panel"><h3>Activity specimen</h3><div class="chart" role="img" aria-label="Example series values: 4, 7, 5, 9, and 6"><span class="chart-bar"></span><span class="chart-bar"></span><span class="chart-bar"></span><span class="chart-bar"></span><span class="chart-bar"></span></div></article><article class="panel stack" aria-busy="true"><h3>Loading-state specimen</h3><div class="skeleton"></div><div class="skeleton" style="width:72%"></div><div class="skeleton" style="width:48%"></div></article></div><div class="panel table-wrap" data-preview="inert"><table class="data-table"><caption>Inert adapter table specimen</caption><thead><tr><th>Adapter</th><th>Mode</th><th>Specimen state</th><th>Example note</th></tr></thead><tbody><tr><td>GTK 4</td><td>Light + dark</td><td><span class="badge primary">Sample A</span></td><td>Example only</td></tr><tr><td>Waybar</td><td>Dark</td><td><span class="badge">Sample B</span></td><td>Example only</td></tr><tr><td>Kitty</td><td>Light + dark</td><td><span class="badge primary">Sample A</span></td><td>Example only</td></tr></tbody></table></div>
  </section>
  <section class="spec-section" id="navigation" aria-labelledby="navigation-title">{section_heading('navigation','Navigation','Tabs, breadcrumb, active routes, search, and pagination.')}
    <div class="grid"><article class="panel"><ol class="breadcrumb" aria-label="Breadcrumb"><li>Forge</li><li>Presets</li><li aria-current="page">Current</li></ol><div class="tabs" role="tablist" aria-label="Asset views"><button class="tab" id="tab-components" role="tab" aria-selected="true" aria-controls="panel-components" tabindex="0">Components</button><button class="tab" id="tab-tokens" role="tab" aria-selected="false" aria-controls="panel-tokens" tabindex="-1">Tokens</button><button class="tab" id="tab-adapters" role="tab" aria-selected="false" aria-controls="panel-adapters" tabindex="-1">Adapters</button></div><div class="tab-panel" id="panel-components" role="tabpanel" aria-labelledby="tab-components">Component specimen view is active.</div><div class="tab-panel" id="panel-tokens" role="tabpanel" aria-labelledby="tab-tokens" hidden>Semantic token diagnostics are active.</div><div class="tab-panel" id="panel-adapters" role="tabpanel" aria-labelledby="tab-adapters" hidden>Native adapter inventory is active.</div><nav class="row" aria-label="Pagination"><button class="button outline">Previous</button><span class="badge primary" aria-current="page">1</span><button class="button ghost">2</button><button class="button outline">Next</button></nav></article><article class="sidebar-demo"><nav class="side" aria-label="Specimen sidebar"><a href="#overview">Overview</a><a href="#navigation" aria-current="page">Components</a><a href="#tokens">Tokens</a></nav><div class="side-content"><label class="label" for="command-search">Command search</label><input class="control" id="command-search" type="search" placeholder="Search commands…"><p class="subtle">Active and inactive sidebar semantics remain independent from the shell.</p></div></article></div>
  </section>
  <section class="spec-section" id="feedback" aria-labelledby="feedback-title">{section_heading('feedback','Feedback','Success, warning, error, empty, and destructive recovery patterns.')}
    <div class="grid"><article class="alert success-alert"><strong>Export complete</strong><span class="subtle">All local assets passed validation.</span></article><article class="alert"><strong>Review recommended</strong><span class="subtle">Sidebar contrast differs from the main surface.</span></article><article class="alert error-alert" role="alert"><strong>Mapping failed</strong><span class="subtle">Correct the missing token before generating.</span></article><article class="empty"><h3>No saved comparisons</h3><p class="subtle">Choose a second preset to begin a comparison.</p><button class="button">Choose preset</button></article><article class="panel stack"><h3>Destructive confirmation</h3><p class="subtle">Deleting generated assets does not change the registry.</p><button class="button destructive">Delete generated assets</button></article></div>
  </section>
  <section class="spec-section" id="tokens" aria-labelledby="tokens-title">{section_heading('tokens','Tokens','Named semantic roles. Values update with the selected preset and mode.')}
    <div class="token-grid">{swatches}</div><div class="panel" style="margin-top:1rem"><h3>Fallback policy</h3><p class="subtle">Missing type tokens fall back to local system sans, serif, or monospace families. Missing spacing and radius use compact local dimensions; semantic colors are never replaced by shell colors.</p></div>
  </section>
</div>"""


SCRIPT = r"""
const themes = JSON.parse(document.getElementById('theme-data').textContent);
const specimen = document.getElementById('specimen');
const selector = document.getElementById('theme-select');
const modeToggle = document.getElementById('mode-toggle');
const darkModeToggle = document.getElementById('dark-mode-toggle');
const live = document.getElementById('live-status');
let mode = 'light';
function applyTheme() {
  const theme = themes.find(item => item.name === selector.value) || themes[0];
  const values = theme.modes[mode];
  for (const property of [...specimen.style]) {
    if (property.startsWith('--')) specimen.style.removeProperty(property);
  }
  Object.entries(values).forEach(([key,value]) => specimen.style.setProperty(`--${key}`, value));
  specimen.dataset.theme = mode;
  specimen.querySelectorAll('[data-theme-title]').forEach(item => item.textContent = theme.title);
  specimen.querySelectorAll('[data-theme-description]').forEach(item => item.textContent = theme.description);
  specimen.querySelectorAll('[data-token-name]').forEach(item => {
    item.textContent = theme.diagnostics[mode][item.dataset.tokenName];
  });
  modeToggle.setAttribute('aria-pressed', String(mode === 'light'));
  darkModeToggle.setAttribute('aria-pressed', String(mode === 'dark'));
  live.textContent = `${theme.title}, ${mode} mode`;
}
selector.addEventListener('change', applyTheme);
modeToggle.addEventListener('click', () => { mode = 'light'; applyTheme(); });
darkModeToggle.addEventListener('click', () => { mode = 'dark'; applyTheme(); });
document.querySelectorAll('.switch').forEach(control => control.addEventListener('click', () => control.setAttribute('aria-checked', String(control.getAttribute('aria-checked') !== 'true'))));
const dialog = document.getElementById('review-dialog');
const dialogOpen = document.getElementById('dialog-open');
dialogOpen.addEventListener('click', () => { dialog.showModal(); document.getElementById('dialog-confirm').focus(); });
document.getElementById('dialog-close').addEventListener('click', () => dialog.close());
document.getElementById('dialog-confirm').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => dialogOpen.focus());
const menuTrigger = document.getElementById('menu-trigger');
const menu = document.getElementById('asset-menu');
const menuItems = [...menu.querySelectorAll('[role=menuitem]')];
function closeMenu(returnFocus = true) { menu.hidden = true; menuTrigger.setAttribute('aria-expanded','false'); if (returnFocus) menuTrigger.focus(); }
menuTrigger.addEventListener('click', () => { const opening = menu.hidden; menu.hidden = !opening; menuTrigger.setAttribute('aria-expanded',String(opening)); if (opening) menuItems[0].focus(); });
menu.addEventListener('keydown', event => { const current = menuItems.indexOf(document.activeElement); if (event.key === 'Escape') closeMenu(); if (event.key === 'ArrowDown') { event.preventDefault(); menuItems[(current + 1) % menuItems.length].focus(); } if (event.key === 'ArrowUp') { event.preventDefault(); menuItems[(current - 1 + menuItems.length) % menuItems.length].focus(); } });
menu.addEventListener('focusout', event => { if (!menu.contains(event.relatedTarget) && event.relatedTarget !== menuTrigger) closeMenu(false); });
menuItems.forEach(item => item.addEventListener('click', () => closeMenu()));
document.addEventListener('click', event => { if (!menu.hidden && !menu.contains(event.target) && event.target !== menuTrigger) closeMenu(false); });
const popoverTrigger = document.getElementById('popover-trigger');
const popover = document.getElementById('token-popover');
popoverTrigger.addEventListener('click', () => { const opening = popover.hidden; popover.hidden = !opening; popoverTrigger.setAttribute('aria-expanded', String(opening)); });
const sheet = document.getElementById('asset-sheet');
const sheetOpen = document.getElementById('sheet-open');
sheetOpen.addEventListener('click', () => { sheet.hidden = false; sheetOpen.setAttribute('aria-expanded','true'); document.getElementById('sheet-close').focus(); });
document.getElementById('sheet-close').addEventListener('click', () => { sheet.hidden = true; sheetOpen.setAttribute('aria-expanded','false'); sheetOpen.focus(); });
const tabs = [...document.querySelectorAll('.tabs [role=tab]')];
function selectTab(tab) { const group = [...tab.closest('[role=tablist]').querySelectorAll('[role=tab]')]; group.forEach(item => { const selected = item === tab; item.setAttribute('aria-selected',String(selected)); item.tabIndex = selected ? 0 : -1; document.getElementById(item.getAttribute('aria-controls')).hidden = !selected; }); tab.focus(); }
tabs.forEach(tab => { tab.addEventListener('click', () => selectTab(tab)); tab.addEventListener('keydown', event => { if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return; event.preventDefault(); const group = [...tab.closest('[role=tablist]').querySelectorAll('[role=tab]')]; const index = group.indexOf(tab); const next = event.key === 'Home' ? 0 : event.key === 'End' ? group.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + group.length) % group.length; selectTab(group[next]); }); });
applyTheme();
function syncInitialScroll() {
  const target = window.location.hash ? document.getElementById(decodeURIComponent(window.location.hash.slice(1))) : null;
  if (target) target.scrollIntoView(); else window.scrollTo(0, 0);
}
syncInitialScroll();
window.addEventListener('load', syncInitialScroll);
"""


def _build_html(themes: list[dict[str, object]]) -> str:
    payload = [theme_payload(theme) for theme in themes]
    default = next((theme for theme in payload if theme["name"] == "graphite"), payload[0])
    options = "".join(
        f'<option value="{html.escape(str(theme["name"]), quote=True)}"{" selected" if theme is default else ""}>{html.escape(str(theme["title"]))}</option>'
        for theme in payload
    )
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    preset_count = len(payload)
    nav = "".join(f'<a href="#{name.lower()}">{name}</a>' for name in SECTIONS if name != "Shell")
    markup = specimen_markup(default) + (
        '<noscript><p class="preview-note">JavaScript is disabled; the default '
        "theme specimen remains available, but theme and mode switching are unavailable."
        "</p></noscript>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; connect-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>Theme Forge — shadcn specimen gallery</title><style>{SHELL_CSS}\n{SPECIMEN_CSS}</style></head>
<body><header class="utility"><div class="brand"><span class="mark" aria-hidden="true"></span><div><span class="eyebrow">Specimen lab</span><strong>Theme Forge</strong></div></div><label class="theme-control"><span class="field-label">Preset</span><select id="theme-select">{options}</select></label><div class="mode-group" aria-label="Color mode"><button class="mode-toggle" id="mode-toggle" type="button" aria-pressed="true">{svg_icon('sun')}Light</button><button class="mode-toggle" id="dark-mode-toggle" type="button" aria-pressed="false">{svg_icon('moon')}Dark</button></div><span class="utility-spacer"></span><div class="status"><span>{preset_count} presets · Offline</span><span class="sr-only" id="live-status" aria-live="polite"></span></div><button class="utility-icon" type="button" aria-label="Open command line">{svg_icon('terminal')}</button><button class="utility-icon" type="button" aria-label="Open settings">{svg_icon('settings')}</button></header><nav class="section-nav" aria-label="Specimen sections">{nav}</nav><div class="gallery-shell"><aside class="gallery-rail"><span class="rail-label">Shadcn lab</span><nav class="rail-nav" aria-label="Gallery navigation">{''.join(f'<a href="#{name.lower()}"><span class="rail-icon" aria-hidden="true">{svg_icon(symbol)}</span>{name}</a>' for name, symbol in zip(SECTIONS, ('home','pointer','check','panel','table','list','message','palette','palette'), strict=True) if name != "Shell")}</nav><div class="rail-divider"></div><span class="rail-label">Utilities</span><nav class="rail-nav" aria-label="Theme utilities"><a href="#tokens"><span class="rail-icon" aria-hidden="true">{svg_icon('palette')}</span>Theme presets <span>{preset_count}</span></a><a href="#data"><span class="rail-icon" aria-hidden="true">{svg_icon('upload')}</span>Export theme</a><a href="#forms"><span class="rail-icon" aria-hidden="true">{svg_icon('download')}</span>Import theme</a><a href="#feedback"><span class="rail-icon" aria-hidden="true">{svg_icon('diff')}</span>Diff viewer</a></nav><div class="rail-divider"></div><span class="rail-label">System</span><nav class="rail-nav" aria-label="System utilities"><a href="#shell"><span class="rail-icon" aria-hidden="true">{svg_icon('check')}</span>Adapter status<span class="adapter-status-dot" aria-hidden="true"></span></a><a href="#data"><span class="rail-icon" aria-hidden="true">{svg_icon('list')}</span>Build logs</a><a href="#forms"><span class="rail-icon" aria-hidden="true">{svg_icon('settings')}</span>Settings</a></nav><div class="rail-foot">Theme Forge v1.0.0<br>Offline mode</div></aside><main class="gallery-main"><div class="specimen-boundary"><div class="boundary-label"><span>Selected theme specimen · shell colors stop here</span><span class="local-note">Offline · local font fallbacks</span></div>{markup}</div></main></div><script type="application/json" id="theme-data">{data}</script><script>{SCRIPT}</script></body></html>"""


def build_html(themes: list[dict[str, object]]) -> str:
    """Build the gallery with source-derived facts and honest specimen labels."""
    source = _build_html(themes)
    shell_copy = {
        'aria-label="Open command line"': 'aria-label="Command-line control specimen"',
        'aria-label="Open settings"': 'aria-label="Settings control specimen"',
        ">Utilities</span>": ">Specimens</span>",
        'aria-label="Theme utilities"': 'aria-label="Theme utility specimens"',
        ">Export theme</a>": ">Export specimen</a>",
        ">Import theme</a>": ">Import specimen</a>",
        ">Diff viewer</a>": ">Diff specimen</a>",
        ">System</span>": ">Diagnostics</span>",
        'aria-label="System utilities"': 'aria-label="Diagnostic specimens"',
        'Adapter status<span class="adapter-status-dot" aria-hidden="true"></span>': "Adapter specimen",
        ">Build logs</a>": ">Build-log specimen</a>",
        ">Settings</a>": ">Settings specimen</a>",
        "Theme Forge v1.0.0": "Local specimen gallery",
        '<article class="shell-card notifications">': '<article class="shell-card notifications" data-preview="inert">',
        "Theme applied": "Success notification specimen",
        "Theme assets are ready.": "Example notification body.",
        "Update available": "Update notification specimen",
        "3 packages can be updated.": "Example notification body.",
        "Assets generated": "Success toast specimen",
        "Six adapters are ready for review.": "Inert copy for reviewing hierarchy and spacing.",
        "Generated assets": "Asset sheet specimen",
        "Inspect native targets without leaving the current section.": "Inspect an inert native-target layout without leaving the current section.",
        "Shown in generated asset metadata.": "Example helper text; no generated metadata is asserted.",
        ">Generated path</label>": ">Readonly path specimen</label>",
        'value="out/themes/current"': 'value="out/example/current"',
        "Export complete": "Success alert specimen",
        "All local assets passed validation.": "Example completion copy; no validation result is asserted.",
        "Deleting generated assets does not change the registry.": "Destructive-action specimen; no files are changed.",
        ">Delete generated assets</button>": ">Delete specimen</button>",
        'aria-label="Inert progress specimen"': 'aria-label="Asset generation progress"',
    }
    for claim, honest_copy in shell_copy.items():
        source = source.replace(claim, honest_copy)
    return source


def verify_gallery(output: Path = OUTPUT_PATH, registry_path: Path = REGISTRY_PATH) -> list[str]:
    """Return validation errors for a generated gallery, or an empty list."""
    errors: list[str] = []
    themes = load_themes(registry_path)
    source = output.read_text(encoding="utf-8") if output.exists() else ""
    if not source:
        return [f"missing gallery output: {output}"]
    payload_match = re.search(r'<script type="application/json" id="theme-data">(.*?)</script>', source, re.S)
    try:
        payload = json.loads(payload_match.group(1).replace("<\\/", "</")) if payload_match else []
    except json.JSONDecodeError as exc:
        errors.append(f"invalid embedded theme data: {exc}")
        payload = []
    if len(payload) != len(themes):
        errors.append(f"gallery contains {len(payload)} presets; registry contains {len(themes)}")
    names = [str(item.get("name", "")) for item in themes]
    payload_names = [str(item.get("name", "")) for item in payload]
    if payload_names != names or len(set(payload_names)) != len(payload_names):
        errors.append("embedded preset names do not exactly match registry order and uniqueness")
    if re.search(r"(?:https?:)?//|@import\s|\bfetch\s*\(|XMLHttpRequest|sendBeacon", source, re.I):
        errors.append("gallery references a remote resource or network API")
    if re.search(r"\{\{.*?\}\}|\{%.*?%\}|__[A-Z][A-Z0-9_]+__", source, re.S):
        errors.append("gallery contains an unresolved placeholder")
    if "data-preset" in source:
        errors.append("gallery contains deprecated preset-specific state metadata")
    specimen_match = re.search(r"/\* SPECIMEN_CSS_START \*/(.*?)/\* SPECIMEN_CSS_END \*/", source, re.S)
    specimen_css = specimen_match.group(1) if specimen_match else ""
    if not specimen_css:
        errors.append("specimen CSS audit markers are missing")
    lowered_specimen_css = specimen_css.lower()
    preset_markers = [
        name for name in names
        if re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", lowered_specimen_css)
    ]
    if "data-preset" in lowered_specimen_css or preset_markers:
        errors.append("specimen CSS contains a preset-specific branch")
    literal_color = re.compile(r"#[0-9a-f]{3,8}\b|(?:oklch|rgb|rgba|hsl|hsla)\([^)]*\)", re.I)
    audited_css = specimen_css
    for extension in re.findall(r"--status-(?:success|warning|info)\s*:[^;}]+", specimen_css):
        audited_css = audited_css.replace(extension, "")
    literals = sorted(set(literal_color.findall(audited_css)))
    if literals:
        errors.append("specimen CSS contains non-allowlisted literal colors: " + ", ".join(literals))
    registry_union = {
        key
        for item in themes
        for group in (item.get("cssVars", {}) or {}).values()
        if isinstance(group, dict)
        for key in group
    }
    referenced = set(re.findall(r"var\(--([a-zA-Z0-9-]+)", specimen_css))
    allowed_fallbacks = {
        "spacing", "radius", "status-success", "status-warning", "status-info", "status-destructive",
        "status-success-surface", "status-warning-surface", "status-info-surface", "status-destructive-surface",
    }
    unknown = sorted(referenced - registry_union - allowed_fallbacks)
    if unknown:
        errors.append("specimen CSS references unknown tokens: " + ", ".join(unknown))
    if "--forge-" in specimen_css:
        errors.append("specimen CSS references shell tokens")
    selectors = " ".join(re.findall(r"(?:^|\})([^{}]+)\{", specimen_css))
    selector_identifiers = set(re.findall(r"[.#]([a-zA-Z][\w-]*)", selectors))
    preset_branches = sorted(set(names) & selector_identifiers)
    if preset_branches:
        errors.append("specimen CSS contains preset-specific styling: " + ", ".join(preset_branches))
    declared_shell_vars = set(re.findall(r"(--[a-zA-Z0-9-]+)\s*:", SHELL_CSS))
    bad_shell_vars = sorted(name for name in declared_shell_vars if not name.startswith("--forge-"))
    if bad_shell_vars:
        errors.append("shell CSS declares unnamespaced variables: " + ", ".join(bad_shell_vars))
    for section in SECTIONS:
        if f'id="{section.lower()}"' not in source:
            errors.append(f"missing {section} section")
    if source != build_html(themes):
        errors.append("generated artifact differs from deterministic registry build")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify the existing output without regenerating it")
    args = parser.parse_args()
    try:
        if not args.verify:
            themes = load_themes()
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_PATH.write_text(build_html(themes), encoding="utf-8")
            print(f"generated {OUTPUT_PATH.relative_to(ROOT)} with {len(themes)} presets")
        errors = verify_gallery()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"gallery generation failed: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"gallery verification failed: {error}", file=sys.stderr)
        return 1
    print(f"verified {OUTPUT_PATH.relative_to(ROOT)}: static checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

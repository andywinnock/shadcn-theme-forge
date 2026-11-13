#!/usr/bin/env python3
"""Deterministic, dependency-free Chromium qualification for the static gallery."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CHROMIUM = Path("/usr/bin/chromium")
DRIVER_RECORD = ROOT / "qa" / "browser-driver.json"
VISUAL_VERDICTS = ROOT / "qa" / "visual-verdicts.json"
GALLERY = ROOT / "out" / "gallery" / "index.html"
EVIDENCE_DIR = ROOT / "out" / "qa"
VIEWPORTS = ((320, 800), (768, 1024), (1024, 768), (1440, 1000))
SCREENSHOT_VIEWPORTS = ((320, 800), (1440, 1000))
REFERENCE_PRESETS = ("graphite", "cyberpunk", "claymorphism", "cosmic-night")
MODES = ("light", "dark")
EXPECTED_CHROMIUM_MAJOR = 151
PROTOCOL_TIMEOUT = 10.0
COLD_READINESS_SAMPLES = 20
THEME_SWITCH_WARMUPS = 5
THEME_SWITCH_SAMPLES = 100


class QAError(RuntimeError):
    """A fail-closed browser qualification error."""


class CDPClient:
    """Small Chrome remote-debugging-pipe client using only the standard library."""

    def __init__(self, *, javascript_enabled: bool = True) -> None:
        if not CHROMIUM.is_file() or not os.access(CHROMIUM, os.X_OK):
            raise QAError(f"required Chromium executable is unavailable: {CHROMIUM}")
        self.profile = Path(tempfile.mkdtemp(prefix="theme-forge-cdp-", dir=EVIDENCE_DIR))
        # Keep Chromium's documented pipe endpoints open across Python's
        # close-fds phase. Reserving 3/4 also prevents os.pipe() from handing
        # us descriptors that collide while the child remaps them.
        reserved = [os.open(os.devnull, os.O_RDONLY), os.open(os.devnull, os.O_WRONLY)]
        command_read, command_write = os.pipe()
        response_read, response_write = os.pipe()

        def child_setup() -> None:
            os.dup2(command_read, 3)
            os.dup2(response_write, 4)

        args = [
            str(CHROMIUM), "--headless=new", "--remote-debugging-pipe",
            f"--user-data-dir={self.profile}", "--no-first-run", "--no-default-browser-check",
            "--disable-background-networking", "--disable-component-update", "--disable-sync",
            "--metrics-recording-only", "--password-store=basic", "--use-mock-keychain",
            "--force-color-profile=srgb", "--lang=en-US", "--disable-features=Translate",
            "--allow-file-access-from-files", "about:blank",
        ]
        try:
            self.process = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                pass_fds=(3, 4, command_read, response_write), preexec_fn=child_setup,
                start_new_session=True,
            )
        except BaseException:
            for descriptor in (command_read, command_write, response_read, response_write, *reserved):
                os.close(descriptor)
            shutil.rmtree(self.profile)
            raise
        for descriptor in reserved:
            os.close(descriptor)
        os.close(command_read)
        os.close(response_write)
        self._writer = os.fdopen(command_write, "wb", buffering=0)
        self._reader = os.fdopen(response_read, "rb", buffering=0)
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._next_id = 1
        self._lock = threading.Lock()
        self._closed = False
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        try:
            target = self.call("Target.createTarget", {"url": "about:blank"})["targetId"]
            self.session_id = self.call(
                "Target.attachToTarget", {"targetId": target, "flatten": True}
            )["sessionId"]
            for domain in ("Page", "Runtime", "Log", "Network"):
                self.call(f"{domain}.enable")
            self.call("Network.setCacheDisabled", {"cacheDisabled": True})
            self.call("Page.addScriptToEvaluateOnNewDocument", {"source": r"""
                addEventListener('DOMContentLoaded', () => requestAnimationFrame(() => {
                  const controls = ['theme-select', 'mode-toggle', 'dark-mode-toggle']
                    .map(id => document.getElementById(id));
                  if (controls.every(control => control && !control.disabled)) {
                    document.documentElement.dataset.qaReady = 'true';
                  }
                }), {once: true});
            """})
            self.call("Emulation.setScriptExecutionDisabled", {"value": not javascript_enabled})
        except BaseException:
            self.close()
            raise

    def _read_loop(self) -> None:
        buffer = bytearray()
        while not self._closed:
            try:
                chunk = self._reader.read(65536)
            except OSError:
                return
            if not chunk:
                return
            buffer.extend(chunk)
            while b"\0" in buffer:
                raw, _, rest = buffer.partition(b"\0")
                buffer = bytearray(rest)
                if not raw:
                    continue
                message = json.loads(raw)
                if "id" in message:
                    pending = self._pending.get(message["id"])
                    if pending:
                        pending.put(message)
                else:
                    self.events.put(message)

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
            message: dict[str, Any] = {"id": request_id, "method": method, "params": params or {}}
            if hasattr(self, "session_id"):
                message["sessionId"] = self.session_id
            self._writer.write(json.dumps(message, separators=(",", ":")).encode() + b"\0")
        try:
            response = response_queue.get(timeout=PROTOCOL_TIMEOUT)
        except queue.Empty as exc:
            detail = ""
            if self.process.poll() is not None and self.process.stderr is not None:
                detail = self.process.stderr.read().decode(errors="replace").strip()
            suffix = f"; Chromium exited {self.process.returncode}: {detail}" if detail else ""
            raise QAError(f"CDP timeout waiting for {method}{suffix}") from exc
        finally:
            self._pending.pop(request_id, None)
        if "error" in response:
            raise QAError(f"CDP {method} failed: {response['error']}")
        return response.get("result", {})

    def evaluate(self, expression: str, *, await_promise: bool = False) -> Any:
        result = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": await_promise,
        })["result"]
        if result.get("subtype") == "error":
            raise QAError(f"browser evaluation failed: {result.get('description')}")
        return result.get("value")

    def drain_events(self) -> list[dict[str, Any]]:
        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return events

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._writer.close()
            self._reader.close()
        except OSError:
            pass
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        try:
            shutil.rmtree(self.profile)
        except OSError as exc:
            raise QAError(f"browser profile cleanup failed: {self.profile}: {exc}") from exc

    def __enter__(self) -> "CDPClient":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def chromium_version() -> str:
    output = subprocess.run(
        [str(CHROMIUM), "--version"], check=True, text=True, capture_output=True, timeout=5
    ).stdout.strip()
    try:
        major = int(output.split()[1].split(".")[0])
    except (IndexError, ValueError) as exc:
        raise QAError(f"cannot parse Chromium version: {output!r}") from exc
    if major != EXPECTED_CHROMIUM_MAJOR:
        raise QAError(
            f"Chromium major drift: expected {EXPECTED_CHROMIUM_MAJOR}, found {major} ({output})"
        )
    return output


def validate_driver_record() -> dict[str, Any]:
    try:
        record = json.loads(DRIVER_RECORD.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QAError(f"invalid selected-driver record: {DRIVER_RECORD}: {exc}") from exc
    if record.get("selected_driver") != "stdlib-cdp" or record.get("implementations") != ["stdlib-cdp"]:
        raise QAError("selected-driver record must select exactly stdlib-cdp")
    primitives = record.get("feasibility", {}).get("primitives", {})
    missing = [name for name, value in primitives.items() if value.get("status") != "pass"]
    if missing or len(primitives) != 8:
        raise QAError(f"selected-driver feasibility record is incomplete: {missing}")
    chromium_version()
    return record


def load_visual_verdicts() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(VISUAL_VERDICTS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QAError(f"invalid visual-verdict record: {VISUAL_VERDICTS}: {exc}") from exc
    if payload.get("schemaVersion") != 1 or payload.get("browserMajor") != EXPECTED_CHROMIUM_MAJOR:
        raise QAError("visual-verdict record has incompatible schema or browser major")
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, dict):
        raise QAError("visual-verdict record must contain a verdict map")
    return verdicts


def configure_page(client: CDPClient, width: int, height: int, *, media: str = "none", scale: float = 1) -> None:
    client.call("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
        "scale": scale, "screenWidth": width, "screenHeight": height,
    })
    features = []
    if media == "reduced-motion":
        features.append({"name": "prefers-reduced-motion", "value": "reduce"})
    if media == "forced-colors":
        features.append({"name": "forced-colors", "value": "active"})
    client.call("Emulation.setEmulatedMedia", {"media": "screen", "features": features})


def navigate(client: CDPClient) -> list[dict[str, Any]]:
    client.drain_events()
    client.call("Page.navigate", {"url": GALLERY.resolve().as_uri()})
    deadline = time.monotonic() + PROTOCOL_TIMEOUT
    collected: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        try:
            event = client.events.get(timeout=0.1)
        except queue.Empty:
            continue
        collected.append(event)
        if event.get("method") == "Page.loadEventFired":
            time.sleep(0.05)
            return collected + client.drain_events()
    raise QAError("page load did not complete")


def preset_names() -> list[str]:
    data = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
    names = [str(item["name"]) for item in data["items"]]
    if len(names) != 36 or len(set(names)) != 36:
        raise QAError(f"expected 36 unique presets, found {len(names)}")
    return names


STRUCTURAL_JS = r"""(() => {
 document.documentElement.style.scrollBehavior='auto'; scrollTo(0,0);
 const actions=[...document.querySelectorAll('a,button,input,select,textarea,[role=tab],[role=switch]')].filter(e=>!e.hidden);
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom}};
 const visible=actions.filter(e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth&&s.visibility!=='hidden'&&s.display!=='none'});
 const scrollContained=e=>{for(let p=e.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),r=p.getBoundingClientRect();if(/auto|scroll/.test(s.overflowX)&&(e.getBoundingClientRect().left<r.left-1||e.getBoundingClientRect().right>r.right+1))return true;}return false};
 const clipped=visible.filter(e=>{const r=e.getBoundingClientRect();return !scrollContained(e)&&(r.left<-1||r.right>document.documentElement.clientWidth+1)}).map(e=>e.id||e.textContent.trim().slice(0,40));
 const intersections=[];
 for(let i=0;i<visible.length;i++){const a=visible[i].getBoundingClientRect();for(let j=i+1;j<visible.length;j++){const b=visible[j].getBoundingClientRect();const area=Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));if(area>4)intersections.push([visible[i].id||visible[i].textContent.trim().slice(0,20),visible[j].id||visible[j].textContent.trim().slice(0,20)]);}}
 const select=document.querySelector('#theme-select'), specimen=document.querySelector('#specimen');
 const table=document.querySelector('.table-wrap'), tr=table.getBoundingClientRect();
 return {preset:select.value,mode:specimen.dataset.theme||'light',viewport:[innerWidth,innerHeight],pageWidth:document.body.scrollWidth,clientWidth:document.documentElement.clientWidth,clipped,intersections,tableContained:tr.right<=document.documentElement.clientWidth+1&&table.scrollWidth>=table.clientWidth,controls:{theme:{visible:rect(select),name:select.labels[0]?.innerText.trim()},light:{visible:rect(document.querySelector('#mode-toggle')),name:document.querySelector('#mode-toggle').innerText.trim()},dark:{visible:rect(document.querySelector('#dark-mode-toggle')),name:document.querySelector('#dark-mode-toggle').innerText.trim()}},tokens:{background:getComputedStyle(specimen).getPropertyValue('--background').trim(),foreground:getComputedStyle(specimen).getPropertyValue('--foreground').trim(),primary:getComputedStyle(specimen).getPropertyValue('--primary').trim()}};
})()"""


def apply_preset(client: CDPClient, preset: str, mode: str) -> None:
    client.evaluate(
        f"(() => {{const s=document.querySelector('#theme-select');s.value={json.dumps(preset)};"
        "s.dispatchEvent(new Event('change',{bubbles:true}));"
        f"document.querySelector('#{'dark-mode-toggle' if mode == 'dark' else 'mode-toggle'}').click();}})()"
    )


def dispatch_key(client: CDPClient, key: str, code: str, virtual_key: int, *, shift: bool = False) -> None:
    modifiers = 8 if shift else 0
    common = {
        "key": key, "code": code, "windowsVirtualKeyCode": virtual_key,
        "nativeVirtualKeyCode": virtual_key, "modifiers": modifiers,
    }
    if key == "Enter":
        common.update({"text": "\r", "unmodifiedText": "\r"})
    elif code == "Space":
        common.update({"text": " ", "unmodifiedText": " "})
    client.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common})
    client.call("Input.dispatchKeyEvent", {"type": "keyUp", **common})


def structural_record(client: CDPClient, preset: str, mode: str, width: int, height: int) -> dict[str, Any]:
    configure_page(client, width, height)
    apply_preset(client, preset, mode)
    deadline = time.monotonic() + 1
    while True:
        result = client.evaluate(STRUCTURAL_JS)
        if not result["intersections"] or time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    errors = []
    if result["preset"] != preset or result["mode"] != mode:
        errors.append("selected preset/mode mismatch")
    if result["pageWidth"] > result["clientWidth"] + 1:
        errors.append("page-level horizontal overflow")
    if result["clipped"]:
        errors.append(f"clipped controls: {result['clipped']}")
    if result["intersections"]:
        errors.append(f"intersecting controls: {result['intersections'][:5]}")
    if not result["tableContained"]:
        errors.append("table overflow is not contained")
    for name, control in result["controls"].items():
        if not control["name"] or control["visible"]["w"] <= 0:
            errors.append(f"{name} control is unnamed or hidden")
    if not all(result["tokens"].values()):
        errors.append("missing token sentinel")
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    return {"id": f"structural/{preset}/{mode}/{width}x{height}", "tier": "structural", "checks": result,
            "hash": hashlib.sha256(canonical).hexdigest(), "errors": errors}


def screenshot(client: CDPClient, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(client.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})["data"])
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def promote_baselines(pairs: list[tuple[Path, Path]], failures: list[str]) -> int:
    """Copy captures only after every non-baseline release assertion passes."""
    if failures:
        return 0
    for transient, baseline in pairs:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(transient, baseline)
    return len(pairs)


def interaction_record(client: CDPClient, preset: str, mode: str) -> dict[str, Any]:
    configure_page(client, 1024, 768)
    apply_preset(client, preset, mode)
    client.evaluate("document.querySelector('#theme-select').focus()")
    dispatch_key(client, "Tab", "Tab", 9)
    tab_focus = client.evaluate("document.activeElement.id")
    dispatch_key(client, "Tab", "Tab", 9, shift=True)
    shift_tab_focus = client.evaluate("document.activeElement.id")
    client.evaluate("document.querySelector('.section-nav a[href=\"#forms\"]').focus()")
    dispatch_key(client, "Enter", "Enter", 13)
    section_hash = client.evaluate("location.hash")
    client.evaluate("document.querySelector('#forms').scrollIntoView();document.querySelector('[role=switch]').focus()")
    switch_before = client.evaluate("document.querySelector('[role=switch]').getAttribute('aria-checked')")
    dispatch_key(client, " ", "Space", 32)
    switch_state = client.evaluate("document.querySelector('[role=switch]').getAttribute('aria-checked')")
    client.evaluate("document.querySelector('#tab-tokens').focus()")
    dispatch_key(client, " ", "Space", 32)
    tab_state = client.evaluate("document.querySelector('#tab-tokens').getAttribute('aria-selected')")
    client.evaluate("document.querySelector('#dialog-open').focus()")
    dispatch_key(client, " ", "Space", 32)
    dialog_open = client.evaluate("document.querySelector('#review-dialog').open")
    ax_open = client.call("Accessibility.getFullAXTree")
    dispatch_key(client, "Escape", "Escape", 27)
    time.sleep(0.05)
    focus_return = client.evaluate("document.activeElement.id")
    client.evaluate("document.querySelector('#sheet-open').focus()")
    dispatch_key(client, " ", "Space", 32)
    client.evaluate("document.querySelector('#sheet-close').focus()")
    dispatch_key(client, " ", "Space", 32)
    client.evaluate("document.querySelector('#menu-trigger').focus()")
    dispatch_key(client, " ", "Space", 32)
    menu_state = client.evaluate("document.querySelector('#menu-trigger').getAttribute('aria-expanded')")
    dispatch_key(client, "Escape", "Escape", 27)
    ax = client.call("Accessibility.getFullAXTree")
    roles = {str((node.get("role") or {}).get("value", "")).lower()
             for tree in (ax_open, ax) for node in tree.get("nodes", [])}
    checks = {"tabFocus": tab_focus, "shiftTabFocus": shift_tab_focus, "sectionHash": section_hash,
              "switchState": switch_state, "tabState": tab_state,
              "dialogOpened": dialog_open, "focusReturn": focus_return, "menuOpened": menu_state,
              "axRoles": sorted(role for role in roles if role)}
    errors = []
    if not tab_focus: errors.append("real Tab input did not move focus")
    if shift_tab_focus != "theme-select": errors.append("real Shift+Tab input did not return to theme control")
    if section_hash != "#forms": errors.append("section control did not activate from real input")
    if switch_state == switch_before: errors.append("switch state did not update")
    if tab_state != "true": errors.append("tab state did not update")
    if not dialog_open or focus_return != "dialog-open": errors.append("dialog/focus return failed")
    if menu_state != "true": errors.append("menu state did not update")
    for role in ("dialog", "tab", "switch", "navigation"):
        if role not in roles: errors.append(f"accessibility tree missing {role}")
    return {"id": f"interaction/{preset}/{mode}/1024x768", "tier": "interaction", "checks": checks, "errors": errors}


def environment_records(client: CDPClient) -> list[dict[str, Any]]:
    records = []
    for scenario in ("reduced-motion", "forced-colors", "zoom-200"):
        configure_page(client, 1024, 768, media=scenario if scenario != "zoom-200" else "none", scale=.5 if scenario == "zoom-200" else 1)
        apply_preset(client, "graphite", "light")
        checks = client.evaluate("(() => ({overflow:document.documentElement.scrollWidth<=document.documentElement.clientWidth+1,reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,forced:matchMedia('(forced-colors: active)').matches,spinner:getComputedStyle(document.querySelector('.spinner')).animationName}))()")
        errors=[]
        if scenario=="reduced-motion" and (not checks["reduced"] or checks["spinner"]!="none"): errors.append("reduced motion not honored")
        if scenario=="forced-colors" and not checks["forced"]: errors.append("forced colors not active")
        if scenario=="zoom-200" and not checks["overflow"]: errors.append("200% zoom overflow")
        records.append({"id":f"environment/{scenario}/graphite/light/1024x768","tier":"environment","checks":checks,"errors":errors})
    start=time.monotonic(); configure_page(client,1024,768); navigate(client)
    ready = client.evaluate("document.documentElement.dataset.qaReady === 'true'")
    ready_ms=(time.monotonic()-start)*1000
    client.evaluate("document.querySelector('#theme-select').focus()")
    input_start=time.monotonic(); dispatch_key(client,"Tab","Tab",9); dispatch_key(client,"Enter","Enter",13)
    input_ms=(time.monotonic()-input_start)*1000
    readiness_errors=[]
    if not ready: readiness_errors.append("deterministic readiness marker missing")
    if ready_ms>=1000: readiness_errors.append("initial interaction readiness exceeded 1s")
    records.append({"id":"environment/cold-readiness/graphite/light/1024x768","tier":"environment","checks":{"readyMs":round(ready_ms,3),"inputLatencyMs":round(input_ms,3),"marker":ready,"underOneSecond":ready_ms<1000},"errors":readiness_errors})
    with CDPClient(javascript_enabled=False) as disabled:
        configure_page(disabled,1024,768); events=navigate(disabled)
        checks=disabled.evaluate("(() => ({sections:document.querySelectorAll('.spec-section').length,tokens:document.querySelectorAll('.token').length,limitation:document.body.innerText.includes('JavaScript')}))()")
        errors=[] if checks["sections"] and checks["tokens"] else ["JavaScript-disabled content missing"]
        if not checks["limitation"]: errors.append("JavaScript-disabled limitation copy missing")
        records.append({"id":"environment/javascript-disabled/graphite/light/1024x768","tier":"environment","checks":checks,"errors":errors})
    return records


def performance_records(client: CDPClient) -> list[dict[str, Any]]:
    cold=[]
    for _ in range(COLD_READINESS_SAMPLES):
        with CDPClient() as fresh:
            configure_page(fresh,1024,768)
            start=time.monotonic(); navigate(fresh)
            ready=fresh.evaluate("document.documentElement.dataset.qaReady === 'true'")
            elapsed=(time.monotonic()-start)*1000
            fresh.evaluate("document.querySelector('#theme-select').focus()")
            dispatch_key(fresh,"Tab","Tab",9); dispatch_key(fresh,"Enter","Enter",13)
            cold.append({"ms":elapsed,"ready":ready})
    script=f"""(async()=>{{const s=document.querySelector('#theme-select'),presets={json.dumps(REFERENCE_PRESETS)},modes={json.dumps(MODES)},samples=[];const change=async(i,record)=>{{const preset=presets[i%presets.length],mode=modes[Math.floor(i/presets.length)%modes.length],focus=document.activeElement?.id||'',section=location.hash,t=performance.now();s.value=preset;s.dispatchEvent(new Event('change',{{bubbles:true}}));document.querySelector(mode==='dark'?'#dark-mode-toggle':'#mode-toggle').click();const expected=getComputedStyle(document.querySelector('#specimen')).getPropertyValue('--background').trim();await new Promise(requestAnimationFrame);if(record)samples.push({{ms:performance.now()-t,preset,mode,tokensMatched:getComputedStyle(document.querySelector('#specimen')).getPropertyValue('--background').trim()===expected,focusPreserved:(document.activeElement?.id||'')===focus,sectionPreserved:location.hash===section}});}};for(let i=0;i<{THEME_SWITCH_WARMUPS};i++)await change(i,false);for(let i=0;i<{THEME_SWITCH_SAMPLES};i++)await change(i,true);return samples}})()"""
    warm=client.evaluate(script,await_promise=True)
    values=sorted(item["ms"] for item in warm)
    p95=values[math.ceil(.95*len(values))-1]
    cold_ok=all(item["ready"] and item["ms"]<1000 for item in cold)
    warm_ok=p95<100 and all(x["tokensMatched"] and x["focusPreserved"] and x["sectionPreserved"] for x in warm)
    return [
      {"id":"performance/cold-readiness","tier":"performance","checks":{"samplesMs":[round(v["ms"],3) for v in cold],"samples":len(cold),"markers":all(v["ready"] for v in cold),"p95Ms":round(sorted(v["ms"] for v in cold)[math.ceil(.95*len(cold))-1],3),"underOneSecond":cold_ok},"errors":[] if cold_ok else ["cold readiness protocol failed"]},
      {"id":"performance/warm-theme-switch","tier":"performance","checks":{"warmups":THEME_SWITCH_WARMUPS,"samples":len(warm),"p95Ms":round(p95,3),"tokensMatched":all(x["tokensMatched"] for x in warm),"focusPreserved":all(x["focusPreserved"] for x in warm),"sectionPreserved":all(x["sectionPreserved"] for x in warm)},"errors":[] if warm_ok else ["theme switch protocol failed"]},
    ]


def run_qa(mode: str) -> dict[str, Any]:
    record=validate_driver_record()
    verdicts=load_visual_verdicts()
    if not GALLERY.is_file(): raise QAError(f"gallery artifact missing: {GALLERY}")
    browser_version=chromium_version(); major=browser_version.split()[1].split('.')[0]
    baseline_dir=ROOT/"tests"/"baselines"/f"chromium-linux-{major}"
    EVIDENCE_DIR.mkdir(parents=True,exist_ok=True)
    structural=[]; visual=[]; interactions=[]; pending_baselines=[]
    with CDPClient() as client:
        configure_page(client,1024,768); startup_events=navigate(client)
        event_errors=[e for e in startup_events if e.get("method") in {"Runtime.exceptionThrown","Log.entryAdded"}]
        requests=[e["params"]["request"]["url"] for e in startup_events if e.get("method")=="Network.requestWillBeSent"]
        external=[url for url in requests if not url.startswith(("file:","data:","about:"))]
        configure_page(client,*VIEWPORTS[0]); navigate(client)
        for width,height in VIEWPORTS:
            for preset in preset_names():
                for color_mode in MODES:
                    item=structural_record(client,preset,color_mode,width,height)
                    if external: item["errors"].append(f"external requests: {external}")
                    if event_errors: item["errors"].append(f"document-start errors: {len(event_errors)}")
                    structural.append(item)
        for preset in REFERENCE_PRESETS:
            for color_mode in MODES:
                for width,height in SCREENSHOT_VIEWPORTS:
                    configure_page(client,width,height,media="reduced-motion"); apply_preset(client,preset,color_mode)
                    client.evaluate(
                        "new Promise(resolve => setTimeout(resolve, 500))",
                        await_promise=True,
                    )
                    client.evaluate(
                        "(()=>{if(document.querySelector('#qa-static-capture'))return;"
                        "const style=document.createElement('style');style.id='qa-static-capture';"
                        "style.textContent='.spinner,.loading-spinner{visibility:hidden!important;animation:none!important}"
                        "*{scrollbar-width:none!important}*::-webkit-scrollbar{display:none!important}';"
                        "document.head.appendChild(style)})()"
                    )
                    name=f"{preset}-{color_mode}-{width}x{height}.png"; transient=EVIDENCE_DIR/"screenshots"/name
                    digest=screenshot(client,transient); expected=baseline_dir/name
                    errors=[]
                    if mode=="update": pending_baselines.append((transient,expected))
                    elif not expected.is_file(): errors.append(f"missing baseline: {expected.relative_to(ROOT)}")
                    elif hashlib.sha256(expected.read_bytes()).hexdigest()!=digest: errors.append("screenshot differs from baseline")
                    visual_id=f"visual/{preset}/{color_mode}/{width}x{height}"
                    verdict=verdicts.get(visual_id)
                    if not verdict: errors.append("missing recorded visual verdict")
                    elif verdict.get("verdict")!="pass" or int(verdict.get("score",0))<90:
                        errors.append(f"visual verdict requires revision: {verdict.get('score',0)}")
                    visual.append({"id":visual_id,"tier":"visual","screenshot":name,"sha256":digest,"structuralRef":f"structural/{preset}/{color_mode}/{width}x{height}","visualVerdict":verdict,"errors":errors})
        for preset in REFERENCE_PRESETS:
            for color_mode in MODES: interactions.append(interaction_record(client,preset,color_mode))
        environment=environment_records(client); performance=performance_records(client)
    manifest={"schemaVersion":1,"driver":"stdlib-cdp","browserVersion":browser_version,"environment":{"os":"linux","dpr":1,"locale":"en-US","colorProfile":"srgb","fonts":"system-ui/ui-monospace local fallbacks"},"records":{"structural":structural,"visual":visual,"interaction":interactions,"environment":environment,"performance":performance}}
    counts={key:len(value) for key,value in manifest["records"].items()}; expected_counts={"structural":288,"visual":16,"interaction":8,"environment":5,"performance":2}
    failures=[error for records in manifest["records"].values() for item in records for error in item["errors"]]
    if counts!=expected_counts: failures.append(f"evidence counts differ: {counts}")
    updated=promote_baselines(pending_baselines,failures) if mode=="update" else 0
    manifest["summary"]={"counts":counts,"failures":failures,"passed":not failures,"updatedBaselines":updated}
    (EVIDENCE_DIR/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return manifest


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True); action.add_argument("--verify",action="store_true"); action.add_argument("--update",action="store_true")
    args=parser.parse_args()
    try:
        manifest=run_qa("update" if args.update else "verify")
    except (QAError,OSError,subprocess.SubprocessError) as exc:
        print(f"browser QA failed: {exc}",file=sys.stderr); return 1
    summary=manifest["summary"]
    print(json.dumps(summary,sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__=="__main__": raise SystemExit(main())

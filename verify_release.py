#!/usr/bin/env python3
"""Fail-closed, repository-local release qualification for Theme Forge."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_JSON = ROOT / "out" / "qa" / "release-summary.json"
DEFAULT_MARKDOWN = ROOT / "out" / "qa" / "release-summary.md"


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    timeout: int = 300


@dataclass
class StageResult:
    name: str
    command: list[str]
    status: str
    returncode: int
    diagnostic: str


def release_stages() -> tuple[Stage, ...]:
    python = sys.executable
    return (
        Stage("generate", (python, "forge.py", "--noctalia-dir", "out/palettes-test")),
        Stage("native-matrix", (python, "templates.py")),
        Stage("native-qt", (python, "native/qt/manage.py", "--mode", "dark")),
        Stage("shell-pack-render", (python, "shell_pack.py")),
        Stage("unit-tests", (python, "-m", "unittest", "discover", "-s", "tests", "-q"), 600),
        Stage(
            "pyright",
            (
                "pyright", "forge.py", "gallery.py", "oklch.py", "templates.py",
                "shell_pack.py", "browser_qa.py", "verify_release.py", "native/qt/manage.py", "tests",
            ),
            600,
        ),
        Stage("gallery-static", (python, "gallery.py", "--verify")),
        Stage("browser-qa", (python, "browser_qa.py", "--verify"), 1800),
        Stage("shell-pack-verify", (python, "shell_pack.py", "verify")),
        Stage("noctalia-config", ("noctalia", "config", "validate", "out/shell-pack/noctalia")),
        Stage("native-noctalia", ("native/noctalia/build_native.sh",), 1800),
    )


def _safe_command(command: Sequence[str]) -> list[str]:
    safe: list[str] = []
    for arg in command:
        value = str(arg)
        try:
            value = str(Path(value).resolve().relative_to(ROOT)) if Path(value).is_absolute() else value
        except ValueError:
            value = Path(value).name
        safe.append(value)
    return safe


def run_stage(stage: Stage) -> StageResult:
    executable = stage.command[0]
    if shutil.which(executable) is None:
        return StageResult(stage.name, _safe_command(stage.command), "failed", 127, f"required executable missing: {executable}")
    try:
        proc = subprocess.run(
            stage.command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=stage.timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        diagnostic = ((exc.stderr or "") if isinstance(exc.stderr, str) else "")[-2000:]
        return StageResult(stage.name, _safe_command(stage.command), "failed", 124, f"timeout after {stage.timeout}s\n{diagnostic}".strip())
    combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
    return StageResult(
        stage.name,
        _safe_command(stage.command),
        "passed" if proc.returncode == 0 else "failed",
        proc.returncode,
        combined[-4000:],
    )


def generated_fingerprint() -> str:
    roots = (
        ROOT / "out" / "css",
        ROOT / "out" / "preview",
        ROOT / "out" / "templates",
        ROOT / "out" / "shell-pack",
        ROOT / "out" / "native" / "qt",
        ROOT / "out" / "index.json",
    )
    digest = hashlib.sha256()
    files = sorted(path for root in roots for path in ([root] if root.is_file() else root.rglob("*") if root.exists() else []) if path.is_file())
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_summary(results: list[StageResult], reproducible: bool, json_path: Path, markdown_path: Path) -> None:
    passed = all(result.status == "passed" for result in results) and reproducible
    payload = {
        "format": 1,
        "status": "passed" if passed else "failed",
        "reproducible_generation": reproducible,
        "manual_gaps": ["Firefox local-file smoke", "Safari/macOS portability"],
        "stages": [asdict(result) for result in results],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = [f"# Release verification: {payload['status']}", "", f"Reproducible generation: {'yes' if reproducible else 'no'}", "", "| Stage | Status | Exit |", "| --- | --- | ---: |"]
    lines.extend(f"| {r.name} | {r.status} | {r.returncode} |" for r in results)
    lines.extend(("", "Manual-only gaps: Firefox local-file smoke; Safari/macOS portability.", ""))
    markdown_path.write_text("\n".join(lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args(argv)

    results: list[StageResult] = []
    first_fingerprint: str | None = None
    reproducible = False
    for stage in release_stages():
        result = run_stage(stage)
        results.append(result)
        print(f"{result.status.upper():6} {result.name}")
        if result.status != "passed":
            break
        if stage.name == "shell-pack-render":
            first_fingerprint = generated_fingerprint()
            for repeat in release_stages()[:3]:
                repeated = run_stage(Stage(f"repro-{repeat.name}", repeat.command, repeat.timeout))
                results.append(repeated)
                print(f"{repeated.status.upper():6} {repeated.name}")
                if repeated.status != "passed":
                    break
            reproducible = all(result.status == "passed" for result in results[-3:]) and first_fingerprint == generated_fingerprint()
            if not reproducible:
                results.append(StageResult("reproducibility", [], "failed", 1, "generated artifact fingerprint changed across two runs"))
                break
    write_summary(results, reproducible, args.json, args.markdown)
    return 0 if results and all(r.status == "passed" for r in results) and reproducible else 1


if __name__ == "__main__":
    raise SystemExit(main())

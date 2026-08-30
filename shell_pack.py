#!/usr/bin/env python3
"""Build and safely install a repo-owned Noctalia v5 shell pack.

The default command renders ``out/shell-pack`` only. Live XDG configuration is
changed solely by the explicit ``apply`` and ``rollback`` subcommands.
"""
from __future__ import annotations

import argparse
import difflib
import errno
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence, cast

from forge import load_registry, noctalia_palette
from templates import (
    ADAPTERS,
    theme_json,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_PACK_DIR = ROOT / "out" / "shell-pack"
MANAGED_CONFIG = "90-shadcn-theme-forge.toml"
OWNER_MARKER = "# Managed by shadcn-theme-forge shell_pack.py; safe to replace."
BACKUP_ROOT = ".shadcn-theme-forge/backups"
DEFAULT_PALETTE = "graphite"

PLACEHOLDER_RE = re.compile(
    r"{{\s*colors\.([a-z0-9_]+)\.default\.hex"
    r"(?:\s*\|\s*set_alpha\s+([0-9.]+))?\s*}}"
)
SECRET_RE = re.compile(r"(?i)(password|secret|token|credential|api[_-]?key)\s*=")


class UnsafeInstallError(RuntimeError):
    """Raised before mutation when a target cannot be owned safely."""


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def xdg_config_home(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve the XDG config root, honoring Noctalia's root override."""
    values = os.environ if env is None else env
    if values.get("NOCTALIA_CONFIG_HOME"):
        root = Path(values["NOCTALIA_CONFIG_HOME"]).expanduser()
    elif values.get("XDG_CONFIG_HOME"):
        root = Path(values["XDG_CONFIG_HOME"]).expanduser()
    else:
        root = (home or Path.home()) / ".config"
    if not root.is_absolute():
        raise ValueError(f"XDG config root must be absolute: {root}")
    return root


def noctalia_config_dir(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    return xdg_config_home(env, home) / "noctalia"


def _shell_config() -> str:
    lines = [
        OWNER_MARKER,
        "# No secrets, credentials, absolute home paths, monitor names, or pinned apps.",
        "",
        "[theme]",
        'mode = "dark"',
        'source = "custom"',
        f'custom_palette = "{DEFAULT_PALETTE}"',
        "pure_black_dark = false",
        "",
        "[theme.templates]",
        "enable_builtin_templates = false",
        "builtin_ids = []",
        "",
    ]
    for adapter in ADAPTERS:
        lines.extend(
            [
                f"[theme.templates.user.{adapter.name}]",
                f'input_path = "$XDG_CONFIG_HOME/noctalia/templates/shadcn/{adapter.filename}"',
                f'output_path = "{adapter.output_path}"',
                "",
            ]
        )
    text = "\n".join(lines)
    if SECRET_RE.search(text) or str(Path.home()) in text:
        raise ValueError("generated shell config contains a secret-like or host-specific value")
    return text


def _render_adapter(template: str, tokens: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name, alpha = match.groups()
        if name not in tokens:
            raise ValueError(f"adapter references unknown token: {name}")
        value = tokens[name]
        if alpha is None:
            return value
        opacity = float(alpha)
        if not 0.0 <= opacity <= 1.0 or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError(f"cannot apply alpha {alpha} to {value}")
        return value + f"{round(opacity * 255):02x}"

    rendered = PLACEHOLDER_RE.sub(replace, template)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("adapter contains unresolved placeholders")
    return rendered


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _build_pack_files() -> tuple[dict[str, bytes], dict[str, object]]:
    registry = load_registry(write_cache=False)
    items = registry.get("items", [])
    palettes = {item["name"]: noctalia_palette(item) for item in items}
    if len(palettes) != 36:
        raise ValueError(f"expected 36 palettes, found {len(palettes)}")
    if DEFAULT_PALETTE not in palettes:
        raise ValueError(f"default palette {DEFAULT_PALETTE!r} is missing")

    files: dict[str, bytes] = {}
    for name in sorted(palettes):
        files[f"noctalia/palettes/{name}.json"] = _json_text(palettes[name]).encode()

    preview = theme_json(palettes[DEFAULT_PALETTE])
    default_tokens = preview["dark"]
    for adapter in ADAPTERS:
        files[f"noctalia/templates/shadcn/{adapter.filename}"] = adapter.template.encode()
        files[f"rendered/{DEFAULT_PALETTE}/{adapter.filename}"] = _render_adapter(adapter.template, default_tokens).encode()

    files[f"noctalia/{MANAGED_CONFIG}"] = _shell_config().encode()
    manifest_files = [
        {"path": path, "sha256": _sha256(data), "size": len(data)}
        for path, data in sorted(files.items())
    ]
    manifest: dict[str, object] = {
        "format": 1,
        "owner": "shadcn-theme-forge",
        "palette_count": len(palettes),
        "adapter_count": len(ADAPTERS),
        "default_palette": DEFAULT_PALETTE,
        "adapter_outputs": {
            adapter.name: adapter.output_path for adapter in ADAPTERS
        },
        "files": manifest_files,
    }
    files["manifest.json"] = _json_text(manifest).encode()
    return files, manifest


def render_pack(pack_dir: Path = DEFAULT_PACK_DIR) -> dict[str, object]:
    """Render a complete deterministic pack, atomically replacing stale output."""
    pack_dir = pack_dir.absolute()
    if pack_dir.is_symlink():
        raise UnsafeInstallError(f"refusing symlink pack directory: {pack_dir}")
    if pack_dir.exists() and not pack_dir.is_dir():
        raise UnsafeInstallError(f"refusing non-directory pack path: {pack_dir}")
    files, manifest = _build_pack_files()
    pack_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{pack_dir.name}.render-", dir=pack_dir.parent))
    staged_pack = staging_root / "pack"
    old_pack = staging_root / "old"
    try:
        for relative, data in sorted(files.items()):
            _write(staged_pack / relative, data)
        if pack_dir.exists():
            os.replace(pack_dir, old_pack)
        try:
            os.replace(staged_pack, pack_dir)
        except BaseException:
            if old_pack.exists():
                os.replace(old_pack, pack_dir)
            raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    return manifest


def _expected_manifest_paths() -> set[Path]:
    names = {item["name"] for item in load_registry(write_cache=False).get("items", [])}
    paths = {Path("noctalia") / "palettes" / f"{name}.json" for name in names}
    for adapter in ADAPTERS:
        paths.add(Path("noctalia") / "templates" / "shadcn" / adapter.filename)
        paths.add(Path("rendered") / DEFAULT_PALETTE / adapter.filename)
    paths.add(Path("noctalia") / MANAGED_CONFIG)
    return paths


def _validated_manifest_entries(manifest_data: bytes) -> dict[Path, dict[str, object]]:
    manifest = json.loads(manifest_data)
    if not isinstance(manifest, dict) or manifest.get("format") != 1:
        raise ValueError("unsupported pack manifest format")
    if manifest.get("owner") != "shadcn-theme-forge":
        raise ValueError("unexpected pack manifest owner")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("pack manifest files must be a list")
    result: dict[Path, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
            raise ValueError("invalid pack manifest file entry")
        path_value = entry["path"]
        digest = entry["sha256"]
        size = entry["size"]
        if not isinstance(path_value, str) or not isinstance(digest, str) or not isinstance(size, int):
            raise ValueError("invalid pack manifest file entry types")
        relative = Path(path_value)
        if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
            raise ValueError(f"unsafe manifest path: {relative}")
        if relative in result:
            raise ValueError(f"duplicate manifest path: {relative}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or size < 0:
            raise ValueError(f"invalid manifest metadata: {relative}")
        result[relative] = entry
    expected = _expected_manifest_paths()
    if set(result) != expected:
        missing = sorted(str(path) for path in expected - set(result))
        extra = sorted(str(path) for path in set(result) - expected)
        raise ValueError(f"manifest target set mismatch; missing={missing}, extra={extra}")
    return result


def _verified_manifest_files(pack_dir: Path) -> dict[Path, bytes]:
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"render the pack first: {manifest_path} is missing")
    entries = _validated_manifest_entries(manifest_path.read_bytes())
    result: dict[Path, bytes] = {}
    for relative, entry in entries.items():
        source = pack_dir / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"pack file is missing or unsafe: {relative}")
        data = source.read_bytes()
        if len(data) != entry["size"] or _sha256(data) != entry["sha256"]:
            raise ValueError(f"pack checksum mismatch: {relative}")
        result[relative] = data
    actual: set[Path] = set()
    for path in pack_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink in pack: {path.relative_to(pack_dir)}")
        if path.is_file():
            actual.add(path.relative_to(pack_dir))
    expected = set(result) | {Path("manifest.json")}
    extras = sorted(str(path) for path in actual - expected)
    if extras:
        raise ValueError(f"unmanifested pack file(s): {', '.join(extras)}")
    return result


def _pack_files(pack_dir: Path) -> dict[Path, bytes]:
    return {
        Path(*relative.parts[1:]): data
        for relative, data in _verified_manifest_files(pack_dir).items()
        if relative.parts[0] == "noctalia"
    }


def _assert_absolute_config_dir(config_dir: Path) -> None:
    if not config_dir.is_absolute():
        raise ValueError(f"Noctalia config directory must be absolute: {config_dir}")


def _assert_no_symlink_ancestors(target: Path) -> None:
    for ancestor in reversed((target.parent, *target.parent.parents)):
        if ancestor.is_symlink():
            raise UnsafeInstallError(f"refusing symlink ancestor: {ancestor}")


def _assert_safe_target(target: Path, relative: Path, root: Path) -> None:
    _assert_absolute_config_dir(root)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise UnsafeInstallError(f"target escapes managed root: {target}") from exc
    _assert_no_symlink_ancestors(target)
    if target.is_symlink():
        raise UnsafeInstallError(f"refusing symlink target: {target}")
    if target.exists() and not target.is_file():
        raise UnsafeInstallError(f"refusing non-file target: {target}")
    if relative == Path(MANAGED_CONFIG) and target.exists():
        text = target.read_text(errors="replace")
        if not text.startswith(OWNER_MARKER):
            raise UnsafeInstallError(
                f"refusing ambiguous config merge: {target} is not forge-managed"
            )


def _output_files(pack_dir: Path, config_dir: Path) -> dict[Path, bytes]:
    _assert_absolute_config_dir(config_dir)
    manifest_files = _verified_manifest_files(pack_dir)
    xdg_root = config_dir.parent
    outputs: dict[Path, bytes] = {}
    for adapter in ADAPTERS:
        prefix = "$XDG_CONFIG_HOME/"
        if not adapter.output_path.startswith(prefix):
            raise ValueError(f"adapter output is not XDG-relative: {adapter.output_path}")
        relative = Path(adapter.output_path.removeprefix(prefix))
        outputs[relative] = manifest_files[Path("rendered") / DEFAULT_PALETTE / adapter.filename]
    return outputs


def plan_install(pack_dir: Path, config_dir: Path) -> list[dict[str, str]]:
    _assert_absolute_config_dir(config_dir)
    actions: list[dict[str, str]] = []
    for relative, desired in sorted(_pack_files(pack_dir).items(), key=lambda item: str(item[0])):
        target = config_dir / relative
        _assert_safe_target(target, relative, config_dir)
        if not target.exists():
            action = "create"
            detail = ""
        else:
            current = target.read_bytes()
            action = "unchanged" if current == desired else "update"
            detail = ""
            if action == "update" and target.suffix in {".toml", ".json", ".css", ".ini", ".conf", ".lua"}:
                detail = "\n".join(
                    difflib.unified_diff(
                        current.decode(errors="replace").splitlines(),
                        desired.decode(errors="replace").splitlines(),
                        fromfile=str(target),
                        tofile=f"{target} (pack)",
                        lineterm="",
                    )
                )
        actions.append({"action": action, "path": str(target), "diff": detail})
    return actions


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
_READ_FLAGS = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW


def _validate_relative_path(relative: Path) -> None:
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts:
        raise UnsafeInstallError(f"unsafe descriptor-relative path: {relative}")


def _open_absolute_directory(path: Path, *, create: bool) -> int:
    _assert_absolute_config_dir(path)
    descriptor = os.open(path.anchor, _DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o755, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise UnsafeInstallError(f"refusing symlink ancestor or non-directory: {path}") from exc
        raise
    except BaseException:
        os.close(descriptor)
        raise


def _open_relative_directory(root_fd: int, relative: Path, *, create: bool) -> int:
    if relative == Path("."):
        return os.dup(root_fd)
    _validate_relative_path(relative)
    descriptor = os.dup(root_fd)
    try:
        for component in relative.parts:
            try:
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o755, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise UnsafeInstallError(
                f"refusing symlink ancestor or non-directory: {relative}"
            ) from exc
        raise
    except BaseException:
        os.close(descriptor)
        raise


def _open_config_roots(config_dir: Path, *, create: bool) -> tuple[int, int]:
    xdg_fd = _open_absolute_directory(config_dir.parent, create=create)
    try:
        config_fd = _open_relative_directory(
            xdg_fd, Path(config_dir.name), create=create
        )
    except BaseException:
        os.close(xdg_fd)
        raise
    return xdg_fd, config_fd


def _pin_target(root_fd: int, relative: Path, *, create_parent: bool) -> tuple[int, str]:
    _validate_relative_path(relative)
    parent_fd = _open_relative_directory(root_fd, relative.parent, create=create_parent)
    return parent_fd, relative.name


def _read_at(parent_fd: int, name: str) -> tuple[bytes, int]:
    descriptor = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise UnsafeInstallError(f"refusing non-file descriptor target: {name}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read(), stat.S_IMODE(details.st_mode)
    finally:
        os.close(descriptor)


def _read_optional_at(parent_fd: int, name: str) -> tuple[bytes, int] | None:
    try:
        return _read_at(parent_fd, name)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise UnsafeInstallError(f"refusing symlink descriptor target: {name}") from exc
        raise


def _assert_pinned_parent(root_fd: int, relative: Path, parent_fd: int) -> None:
    try:
        current_fd = _open_relative_directory(root_fd, relative.parent, create=False)
    except (FileNotFoundError, OSError, UnsafeInstallError) as exc:
        raise UnsafeInstallError(f"target parent changed after validation: {relative.parent}") from exc
    try:
        pinned = os.fstat(parent_fd)
        current = os.fstat(current_fd)
        if (pinned.st_dev, pinned.st_ino) != (current.st_dev, current.st_ino):
            raise UnsafeInstallError(f"target parent changed after validation: {relative.parent}")
    finally:
        os.close(current_fd)


def _atomic_write_at(parent_fd: int, name: str, data: bytes, *, mode: int) -> None:
    temporary = f".{name}.{os.getpid()}.{secrets.token_hex(8)}"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        mode,
        dir_fd=parent_fd,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            os.fchmod(descriptor, mode)
            handle.write(data)
            handle.flush()
            os.fsync(descriptor)
        os.rename(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=parent_fd)
        except FileNotFoundError:
            pass


def _secure_atomic_write(
    root_fd: int,
    parent_fd: int,
    relative: Path,
    data: bytes,
    *,
    mode: int,
) -> None:
    _assert_pinned_parent(root_fd, relative, parent_fd)
    _atomic_write_at(parent_fd, relative.name, data, mode=mode)


def _unlink_at(parent_fd: int, name: str) -> None:
    os.unlink(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _journal_text(record: Mapping[str, object]) -> bytes:
    return _json_text(record).encode()


def _backup_relative(change: Mapping[str, object]) -> Path:
    section = "files" if change["scope"] == "config" else "outputs"
    return Path(section) / str(change["path"])


def _validate_rollback_record(
    config_dir: Path,
    backup_fd: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        record_data, _record_mode = _read_at(backup_fd, "rollback.json")
        record = json.loads(record_data)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise UnsafeInstallError("invalid rollback metadata") from exc
    required = {"format", "owner", "status", "config_root", "manifest_sha256", "changes"}
    if not isinstance(record, dict) or set(record) != required:
        raise UnsafeInstallError("invalid rollback metadata fields")
    if record["format"] != 2 or record["owner"] != "shadcn-theme-forge":
        raise UnsafeInstallError("invalid rollback metadata identity")
    if record["status"] != "complete":
        raise UnsafeInstallError(f"rollback journal is not complete: {record['status']!r}")
    if record["config_root"] != str(config_dir.resolve()):
        raise UnsafeInstallError("rollback metadata is bound to a different config root")
    try:
        manifest_data, _manifest_mode = _read_at(backup_fd, "manifest.json")
    except FileNotFoundError as exc:
        raise UnsafeInstallError("rollback manifest is missing") from exc
    if _sha256(manifest_data) != record["manifest_sha256"]:
        raise UnsafeInstallError("rollback manifest checksum mismatch")
    try:
        manifest_entries = _validated_manifest_entries(manifest_data)
    except (ValueError, json.JSONDecodeError) as exc:
        raise UnsafeInstallError(f"invalid rollback manifest: {exc}") from exc
    allowed_config = {
        Path(*path.parts[1:]): entry["sha256"]
        for path, entry in manifest_entries.items()
        if path.parts[0] == "noctalia"
    }
    allowed_outputs = {
        Path(adapter.output_path.removeprefix("$XDG_CONFIG_HOME/")): manifest_entries[
            Path("rendered") / DEFAULT_PALETTE / adapter.filename
        ]["sha256"]
        for adapter in ADAPTERS
    }
    changes = record["changes"]
    if not isinstance(changes, list) or not changes:
        raise UnsafeInstallError("invalid rollback metadata changes")
    validated: list[dict[str, object]] = []
    seen: set[tuple[str, Path]] = set()
    fields = {
        "scope",
        "path",
        "disposition",
        "installed_sha256",
        "installed_mode",
        "original_sha256",
        "original_mode",
    }
    for raw in changes:
        if not isinstance(raw, dict) or set(raw) != fields:
            raise UnsafeInstallError("invalid rollback metadata change fields")
        scope = raw["scope"]
        disposition = raw["disposition"]
        relative = Path(str(raw["path"]))
        allowed = allowed_config if scope == "config" else allowed_outputs if scope == "output" else {}
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative not in allowed
            or (scope, relative) in seen
        ):
            raise UnsafeInstallError(f"invalid rollback metadata target: {scope}:{relative}")
        seen.add((str(scope), relative))
        if disposition not in {"created", "overwritten"}:
            raise UnsafeInstallError("invalid rollback metadata disposition")
        if not isinstance(raw["installed_mode"], int) or not 0 <= raw["installed_mode"] <= 0o7777:
            raise UnsafeInstallError("invalid rollback metadata installed mode")
        if not isinstance(raw["installed_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", raw["installed_sha256"]
        ):
            raise UnsafeInstallError("invalid rollback metadata installed checksum")
        if raw["installed_sha256"] != allowed[relative]:
            raise UnsafeInstallError("rollback metadata checksum is not bound to its manifest target")
        if disposition == "created":
            if raw["original_sha256"] is not None or raw["original_mode"] is not None:
                raise UnsafeInstallError("invalid rollback metadata for created target")
        else:
            if not isinstance(raw["original_sha256"], str) or not re.fullmatch(
                r"[0-9a-f]{64}", raw["original_sha256"]
            ):
                raise UnsafeInstallError("invalid rollback metadata original checksum")
            if not isinstance(raw["original_mode"], int) or not 0 <= raw["original_mode"] <= 0o7777:
                raise UnsafeInstallError("invalid rollback metadata original mode")
        validated.append(raw)
    return record, validated


def apply_pack(
    pack_dir: Path,
    config_dir: Path,
    *,
    timestamp: str | None = None,
) -> Path | None:
    _assert_absolute_config_dir(config_dir)
    files = _pack_files(pack_dir)
    xdg_fd, config_fd = _open_config_roots(config_dir, create=True)
    backup_fd: int | None = None
    journal_parent_fd: int | None = None
    pinned_fds: list[int] = []
    try:
        desired_specs = [
            ("config", relative, desired)
            for relative, desired in sorted(files.items(), key=lambda item: str(item[0]))
        ]
        runtime_changes: list[tuple[int, int, Path, bytes, bytes | None, dict[str, object]]] = []
        record_changes: list[dict[str, object]] = []
        for scope, relative, desired in desired_specs:
            root_fd = config_fd if scope == "config" else xdg_fd
            parent_fd, name = _pin_target(root_fd, relative, create_parent=True)
            current = _read_optional_at(parent_fd, name)
            if relative == Path(MANAGED_CONFIG) and current is not None:
                if not current[0].decode(errors="replace").startswith(OWNER_MARKER):
                    os.close(parent_fd)
                    raise UnsafeInstallError(
                        f"refusing ambiguous config merge: {config_dir / relative} is not forge-managed"
                    )
            if current is not None and current[0] == desired:
                os.close(parent_fd)
                continue
            original_data = current[0] if current is not None else None
            original_mode = current[1] if current is not None else None
            installed_mode = original_mode if original_mode is not None else 0o644
            change: dict[str, object] = {
                "scope": scope,
                "path": str(relative),
                "disposition": "overwritten" if current is not None else "created",
                "installed_sha256": _sha256(desired),
                "installed_mode": installed_mode,
                "original_sha256": _sha256(original_data) if original_data is not None else None,
                "original_mode": original_mode,
            }
            pinned_fds.append(parent_fd)
            record_changes.append(change)
            runtime_changes.append((root_fd, parent_fd, relative, desired, original_data, change))
        if not runtime_changes:
            return None

        stamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path_relative = Path(BACKUP_ROOT) / stamp
        try:
            backup_fd = _open_relative_directory(config_fd, backup_path_relative, create=False)
        except FileNotFoundError:
            backup_fd = _open_relative_directory(config_fd, backup_path_relative, create=True)
        else:
            raise UnsafeInstallError(f"backup already exists: {config_dir / backup_path_relative}")
        backup_dir = config_dir / backup_path_relative
        manifest_data = (pack_dir / "manifest.json").read_bytes()
        manifest_parent_fd, _manifest_name = _pin_target(
            backup_fd, Path("manifest.json"), create_parent=True
        )
        try:
            _secure_atomic_write(
                backup_fd,
                manifest_parent_fd,
                Path("manifest.json"),
                manifest_data,
                mode=0o644,
            )
        finally:
            os.close(manifest_parent_fd)
        for _root_fd, _parent_fd, _relative, _desired, original_data, change in runtime_changes:
            if original_data is None:
                continue
            payload_relative = _backup_relative(change)
            payload_parent_fd, _payload_name = _pin_target(
                backup_fd, payload_relative, create_parent=True
            )
            try:
                _secure_atomic_write(
                    backup_fd,
                    payload_parent_fd,
                    payload_relative,
                    original_data,
                    mode=cast(int, change["original_mode"]),
                )
            finally:
                os.close(payload_parent_fd)
        record: dict[str, object] = {
            "format": 2,
            "owner": "shadcn-theme-forge",
            "status": "prepared",
            "config_root": str(config_dir.resolve()),
            "manifest_sha256": _sha256(manifest_data),
            "changes": record_changes,
        }
        journal_relative = Path("rollback.json")
        journal_parent_fd, _journal_name = _pin_target(
            backup_fd, journal_relative, create_parent=True
        )
        _secure_atomic_write(
            backup_fd,
            journal_parent_fd,
            journal_relative,
            _journal_text(record),
            mode=0o600,
        )
        applied: list[tuple[int, int, Path, bytes | None, dict[str, object]]] = []
        try:
            for root_fd, parent_fd, relative, desired, original_data, change in runtime_changes:
                applied.append((root_fd, parent_fd, relative, original_data, change))
                _secure_atomic_write(
                    root_fd,
                    parent_fd,
                    relative,
                    desired,
                    mode=cast(int, change["installed_mode"]),
                )
            record["status"] = "complete"
            _secure_atomic_write(
                backup_fd,
                journal_parent_fd,
                journal_relative,
                _journal_text(record),
                mode=0o600,
            )
        except BaseException as exc:
            recovery_errors: list[str] = []
            for _root_fd, parent_fd, relative, original_data, change in reversed(applied):
                try:
                    if change["disposition"] == "created":
                        try:
                            _unlink_at(parent_fd, relative.name)
                        except FileNotFoundError:
                            pass
                    else:
                        assert original_data is not None
                        _atomic_write_at(
                            parent_fd,
                            relative.name,
                            original_data,
                            mode=cast(int, change["original_mode"]),
                        )
                except BaseException as recovery_exc:
                    recovery_errors.append(f"{relative}: {recovery_exc}")
            record["status"] = "recovery-failed" if recovery_errors else "reversed"
            _atomic_write_at(
                journal_parent_fd,
                journal_relative.name,
                _journal_text(record),
                mode=0o600,
            )
            if recovery_errors:
                raise UnsafeInstallError(
                    "apply failed and automatic reversal was incomplete: "
                    + "; ".join(recovery_errors)
                ) from exc
            raise
        return backup_dir
    finally:
        for descriptor in pinned_fds:
            os.close(descriptor)
        if journal_parent_fd is not None:
            os.close(journal_parent_fd)
        if backup_fd is not None:
            os.close(backup_fd)
        os.close(config_fd)
        os.close(xdg_fd)


def rollback(config_dir: Path, backup_dir: Path | None = None) -> Path:
    _assert_absolute_config_dir(config_dir)
    root = config_dir / BACKUP_ROOT
    xdg_fd, config_fd = _open_config_roots(config_dir, create=False)
    try:
        backup_root_fd = _open_relative_directory(
            config_fd, Path(BACKUP_ROOT), create=False
        )
    except BaseException:
        os.close(config_fd)
        os.close(xdg_fd)
        raise
    selected_fd: int | None = None
    journal_parent_fd: int | None = None
    pinned_fds: list[int] = []
    try:
        if backup_dir is None:
            candidates = sorted(name for name in os.listdir(backup_root_fd) if name not in {".", ".."})
            if not candidates:
                raise FileNotFoundError(f"no backups under {root}")
            backup_name = candidates[-1]
            backup_dir = root / backup_name
        else:
            if not backup_dir.is_absolute():
                backup_dir = backup_dir.absolute()
            if backup_dir.parent.resolve() != root.resolve():
                raise UnsafeInstallError(f"backup is outside managed backup root: {backup_dir}")
            backup_name = backup_dir.name
        _validate_relative_path(Path(backup_name))
        selected_fd = _open_relative_directory(
            backup_root_fd, Path(backup_name), create=False
        )
        record, changes = _validate_rollback_record(config_dir, selected_fd)
        runtime_changes: list[
            tuple[int, int, Path, dict[str, object], bytes | None]
        ] = []
        conflicts: list[str] = []
        for change in changes:
            scope = str(change["scope"])
            relative = Path(str(change["path"]))
            target_root_fd = config_fd if scope == "config" else xdg_fd
            parent_fd, name = _pin_target(target_root_fd, relative, create_parent=False)
            pinned_fds.append(parent_fd)
            current = _read_optional_at(parent_fd, name)
            display_root = config_dir if scope == "config" else config_dir.parent
            target = display_root / relative
            if current is None:
                conflicts.append(f"{target} is missing")
                runtime_changes.append((target_root_fd, parent_fd, relative, change, None))
                continue
            current_data, current_mode = current
            if _sha256(current_data) != change["installed_sha256"] or current_mode != change[
                "installed_mode"
            ]:
                conflicts.append(f"{target} changed after apply")
            original_data: bytes | None = None
            if change["disposition"] == "overwritten":
                payload_relative = _backup_relative(change)
                payload_parent_fd, payload_name = _pin_target(
                    selected_fd, payload_relative, create_parent=False
                )
                try:
                    original_data, _payload_mode = _read_at(payload_parent_fd, payload_name)
                finally:
                    os.close(payload_parent_fd)
                if _sha256(original_data) != change["original_sha256"]:
                    raise UnsafeInstallError(
                        f"backup payload checksum mismatch: {backup_dir / payload_relative}"
                    )
            runtime_changes.append(
                (target_root_fd, parent_fd, relative, change, original_data)
            )
        if conflicts:
            raise UnsafeInstallError(
                "rollback conflict; no files changed: " + "; ".join(conflicts)
            )
        for target_root_fd, parent_fd, relative, change, original_data in reversed(
            runtime_changes
        ):
            _assert_pinned_parent(target_root_fd, relative, parent_fd)
            if change["disposition"] == "created":
                _unlink_at(parent_fd, relative.name)
            else:
                assert original_data is not None
                _atomic_write_at(
                    parent_fd,
                    relative.name,
                    original_data,
                    mode=cast(int, change["original_mode"]),
                )
        record["status"] = "rolled-back"
        journal_relative = Path("rollback.json")
        journal_parent_fd, _journal_name = _pin_target(
            selected_fd, journal_relative, create_parent=False
        )
        _secure_atomic_write(
            selected_fd,
            journal_parent_fd,
            journal_relative,
            _journal_text(record),
            mode=0o600,
        )
        return backup_dir
    finally:
        for descriptor in pinned_fds:
            os.close(descriptor)
        if journal_parent_fd is not None:
            os.close(journal_parent_fd)
        if selected_fd is not None:
            os.close(selected_fd)
        os.close(backup_root_fd)
        os.close(config_fd)
        os.close(xdg_fd)


def verify_pack(pack_dir: Path, config_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        manifest_files = _verified_manifest_files(pack_dir)
        files = {
            Path(*relative.parts[1:]): data
            for relative, data in manifest_files.items()
            if relative.parts[0] == "noctalia"
        }
    except (FileNotFoundError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return [str(exc)]
    palette_count = sum(1 for path in files if path.parts[:1] == ("palettes",))
    template_count = sum(1 for path in files if path.parts[:2] == ("templates", "shadcn"))
    if palette_count != 36:
        errors.append(f"expected 36 palettes, found {palette_count}")
    if template_count != 7:
        errors.append(f"expected 7 adapters, found {template_count}")
    config = files.get(Path(MANAGED_CONFIG), b"").decode(errors="replace")
    if not config.startswith(OWNER_MARKER):
        errors.append("managed config marker is missing")
    if SECRET_RE.search(config) or str(Path.home()) in config:
        errors.append("managed config contains secret-like or host-specific data")
    rendered = [
        relative
        for relative in manifest_files
        if relative.parts[:2] == ("rendered", DEFAULT_PALETTE)
    ]
    if len(rendered) != 7:
        errors.append(f"expected 7 rendered adapter outputs, found {len(rendered)}")
    for relative in rendered:
        data = manifest_files[relative].decode(errors="replace")
        if "{{" in data or "}}" in data:
            errors.append(f"unresolved adapter output: {pack_dir / relative}")
    if config_dir is not None:
        for relative, desired in files.items():
            target = config_dir / relative
            if not target.is_file() or target.read_bytes() != desired:
                errors.append(f"installed file differs: {target}")
    return errors


def noctalia_command(operation: str, *, config_dir: Path, palette: str = DEFAULT_PALETTE) -> list[str]:
    """Construct only the four explicitly supported Noctalia argv forms."""
    commands = {
        "validate": ["noctalia", "config", "validate", str(config_dir)],
        "config-reload": ["noctalia", "msg", "config-reload"],
        "color-scheme": ["noctalia", "msg", "color-scheme-set", "custom", palette],
        "templates-apply": ["noctalia", "msg", "templates-apply"],
    }
    if operation not in commands:
        raise ValueError(f"Noctalia operation is not allowlisted: {operation}")
    if operation == "color-scheme" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", palette):
        raise ValueError(f"unsafe palette name: {palette!r}")
    return commands[operation]


def activate(config_dir: Path, palette: str = DEFAULT_PALETTE) -> None:
    _assert_absolute_config_dir(config_dir)
    active_config = noctalia_config_dir()
    if config_dir.resolve() != active_config.resolve():
        raise UnsafeInstallError(
            f"refusing live IPC for non-active Noctalia config: {config_dir}; active: {active_config}"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", palette):
        raise ValueError(f"unsafe palette name: {palette!r}")
    managed_config = config_dir / MANAGED_CONFIG
    _assert_safe_target(managed_config, Path(MANAGED_CONFIG), config_dir)
    if not managed_config.is_file():
        raise UnsafeInstallError(f"forge-managed shell config is not installed: {managed_config}")
    config_text = managed_config.read_text(errors="replace")
    if not config_text.startswith(OWNER_MARKER):
        raise UnsafeInstallError(f"forge-managed shell config is not installed: {managed_config}")
    try:
        config_data = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError as exc:
        raise UnsafeInstallError(f"installed shell config is invalid TOML: {managed_config}") from exc
    if config_data.get("theme", {}).get("source") != "custom":
        raise UnsafeInstallError(f"installed shell config does not enable custom palettes: {managed_config}")
    palette_path = config_dir / "palettes" / f"{palette}.json"
    _assert_safe_target(palette_path, Path("palettes") / f"{palette}.json", config_dir)
    if not palette_path.is_file():
        raise UnsafeInstallError(f"installed palette is missing: {palette_path}")
    try:
        palette_data = json.loads(palette_path.read_text())
    except json.JSONDecodeError as exc:
        raise UnsafeInstallError(f"installed palette is invalid JSON: {palette_path}") from exc
    if not isinstance(palette_data, dict):
        raise UnsafeInstallError(f"installed palette is not an object: {palette_path}")
    for operation in ("validate", "config-reload", "color-scheme", "templates-apply"):
        subprocess.run(
            noctalia_command(operation, config_dir=config_dir, palette=palette),
            check=True,
            shell=False,
        )


def _print_plan(actions: Sequence[Mapping[str, str]]) -> None:
    for action in actions:
        print(f"{action['action']:18} {action['path']}")
        if action.get("diff"):
            print(action["diff"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="render",
        choices=("render", "plan", "apply", "verify", "rollback", "activate"),
    )
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="required confirmation for live file or state changes",
    )
    parser.add_argument("--installed", action="store_true", help="verify installed XDG files too")
    parser.add_argument(
        "--activate",
        metavar="PALETTE",
        help="with activate, run allowlisted Noctalia commands for the active profile",
    )
    parser.add_argument("--backup", type=Path, help="specific managed backup for rollback")
    args = parser.parse_args(argv)
    config_dir = args.config_dir or noctalia_config_dir()
    try:
        if args.command == "render":
            manifest = render_pack(args.pack_dir)
            print(f"rendered {manifest['palette_count']} palettes and {manifest['adapter_count']} adapters -> {args.pack_dir}")
        elif args.command == "plan":
            _print_plan(plan_install(args.pack_dir, config_dir))
            print("dry-run only; no user files changed")
        elif args.command == "apply":
            if not args.apply:
                raise UnsafeInstallError("live installation requires the explicit --apply flag")
            if args.activate:
                raise UnsafeInstallError(
                    "file apply and live state are separate; run the separate activate command"
                )
            backup = apply_pack(args.pack_dir, config_dir)
            print("already current" if backup is None else f"applied; backup: {backup}")
        elif args.command == "verify":
            errors = verify_pack(args.pack_dir, config_dir if args.installed else None)
            if errors:
                print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
                return 1
            print("verify: pack is complete" + (" and installed files match" if args.installed else ""))
        elif args.command == "rollback":
            restored = rollback(config_dir, args.backup)
            print(f"rolled back from {restored}")
        else:
            if not args.activate:
                raise UnsafeInstallError("activate requires --activate PALETTE")
            if not args.apply:
                raise UnsafeInstallError("live activation requires the explicit --apply flag")
            activate(config_dir, args.activate)
            print(f"activated live Noctalia palette: {args.activate}")
    except (FileNotFoundError, ValueError, UnsafeInstallError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

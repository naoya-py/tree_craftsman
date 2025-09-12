"""
tools/bump_version.py

Atomic write -> validate -> replace flow for pyproject.toml and setup.cfg.
API:
  - update_files(repo_root: str, new_version: str) -> None
    Raises:
      ValueError, ValidationError, RecoveryError, RuntimeError/OSError
  - main() handles SystemExit codes:
    0: success
    2: invalid usage / input
    3: validation failed (backup restored)
    4: recovery failed / IO error
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import tempfile
import time
from typing import Optional, Tuple

# TOML loader: prefer tomllib (py3.11+), fallback to toml package
try:
    import tomllib as _toml_loader  # type: ignore
    _HAS_TOML_STD = True
except Exception:
    try:
        import toml as _toml_loader  # type: ignore
        _HAS_TOML_STD = False
    except Exception:
        _toml_loader = None
        _HAS_TOML_STD = False

import configparser
import glob

RE_SEMVER = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].*)?$")


class BumpError(Exception):
    pass


class ValidationError(BumpError):
    """Updated file failed syntax validation; backup restored successfully."""


class RecoveryError(BumpError):
    """Recovery from backup failed or backup missing."""


def parse_version(arg: str) -> str:
    m = RE_SEMVER.match(arg)
    if not m:
        raise ValueError(f"Invalid version: {arg!s}")
    return f"{m.group('major')}.{m.group('minor')}.{m.group('patch')}"


def _backup_file(path: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    return bak


def _write_tmp_and_validate(path: str, content: str, kind: str = "toml") -> bool:
    """
    Write content to a tmp file next to target, validate using parser,
    but DO NOT replace target here. Return True if validation OK.
    """
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_bump_", dir=dirpath, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        with open(tmp, "r", encoding="utf-8") as f:
            txt = f.read()
        if kind == "toml":
            if _toml_loader is None:
                raise RuntimeError("No TOML parser available (install 'toml' or use Python 3.11+)")
            try:
                if _HAS_TOML_STD:
                    # tomllib.loads expects bytes for some implementations; accept str by encode
                    _toml_loader.loads(txt.encode("utf-8") if isinstance(txt, str) else txt)  # type: ignore
                else:
                    _toml_loader.loads(txt)  # type: ignore
            except Exception:
                return False
        else:
            cp = configparser.ConfigParser()
            try:
                cp.read_string(txt)
            except Exception:
                return False
        return True
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _atomic_replace_from_tmp(path: str, content: str) -> None:
    """Write content to tmp file then os.replace to path (atomic)."""
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_bump_replace_", dir=dirpath, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def generate_updated_text_for_pyproject(orig_text: str, new_version: str) -> Tuple[str, bool]:
    """
    Return (updated_text, changed_flag).
    Minimal toml-style replacement for [tool.poetry] and [project].
    """
    lines = orig_text.splitlines(keepends=True)
    out_lines = lines.copy()

    def replace_in_section(lines_in, section):
        out = []
        in_section = False
        rep = False
        for line in lines_in:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_section = (stripped == section)
            if in_section and not rep:
                m = re.match(r'^(version\s*=\s*)"([^"]+)"\s*$', line)
                if m:
                    out.append(f'{m.group(1)}"{new_version}"\n')
                    rep = True
                    continue
            out.append(line)
        return out, rep

    tmp, r1 = replace_in_section(out_lines, "[tool.poetry]")
    tmp, r2 = replace_in_section(tmp, "[project]")
    changed = bool(r1 or r2)
    return ("".join(tmp), changed)


def generate_updated_text_for_setupcfg(orig_text: str, new_version: str) -> Tuple[str, bool]:
    lines = orig_text.splitlines(keepends=True)
    out = []
    in_metadata = False
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_metadata = (stripped.lower() == "[metadata]")
        if in_metadata and not replaced:
            m = re.match(r'^(version\s*=\s*)(.+)\s*$', line)
            if m:
                out.append(f"{m.group(1)}{new_version}\n")
                replaced = True
                continue
        out.append(line)
    return ("".join(out), replaced)


def update_files(repo_root: str, new_version: str) -> None:
    """
    Update supported files. Raises exceptions on failure.
    """
    if not new_version:
        raise ValueError("new_version required")

    # pyproject.toml
    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.exists(pyproject):
        with open(pyproject, "r", encoding="utf-8") as f:
            orig = f.read()
        updated_text, changed = generate_updated_text_for_pyproject(orig, new_version)
        if changed:
            bak = _backup_file(pyproject)
            ok = _write_tmp_and_validate(pyproject, updated_text, kind="toml")
            if not ok:
                # validation failed -> attempt recovery from backup
                try:
                    os.replace(bak, pyproject)
                except Exception:
                    raise RecoveryError("Validation failed and recovery failed for pyproject.toml")
                raise ValidationError("Updated pyproject.toml failed TOML validation; backup restored")
            _atomic_replace_from_tmp(pyproject, updated_text)

    # setup.cfg
    setup_cfg = os.path.join(repo_root, "setup.cfg")
    if os.path.exists(setup_cfg):
        with open(setup_cfg, "r", encoding="utf-8") as f:
            orig = f.read()
        updated_text, changed = generate_updated_text_for_setupcfg(orig, new_version)
        if changed:
            bak = _backup_file(setup_cfg)
            ok = _write_tmp_and_validate(setup_cfg, updated_text, kind="ini")
            if not ok:
                try:
                    os.replace(bak, setup_cfg)
                except Exception:
                    raise RecoveryError("Validation failed and recovery failed for setup.cfg")
                raise ValidationError("Updated setup.cfg failed INI validation; backup restored")
            _atomic_replace_from_tmp(setup_cfg, updated_text)


def main(argv: Optional[list[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: bump_version.py <new_version>", file=sys.stderr)
        raise SystemExit(2)
    try:
        new_version = parse_version(argv[0])
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        update_files(repo_root, new_version)
    except ValidationError as exc:
        print(f"ValidationError: {exc}", file=sys.stderr)
        raise SystemExit(3)
    except RecoveryError as exc:
        print(f"RecoveryError: {exc}", file=sys.stderr)
        raise SystemExit(4)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(4)
    print(f"Updated version -> {new_version}", file=sys.stderr)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
"""Minimal bump utility used by tests.

Features implemented (subset needed for unit tests):
- update pyproject.toml for [project] and [tool.poetry]
- update setup.cfg [metadata] version
- create timestamped backups before attempting changes
- validate TOML/INI after generating new text; raise ValidationError on failure
"""
from __future__ import annotations

import configparser
import os
import shutil
import tempfile
import time
import re
from pathlib import Path
import sys

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - CI uses 3.11+
    tomllib = None


class BumpError(Exception):
    pass


class ValidationError(BumpError):
    pass


class RecoveryError(BumpError):
    pass


def parse_version(v: str) -> str:
    if v.startswith("v"):
        v = v[1:]
    # simple sanity check: digits and dots
    if not re.fullmatch(r"\d+(?:\.\d+)*", v):
        raise ValueError(f"invalid version: {v!r}")
    return v


def _timestamp() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def _backup_file(path: Path) -> Path:
    bak = path.with_name(path.name + ".bak." + _timestamp())
    shutil.copy2(path, bak)
    return bak


def _write_temp(path: Path, content: str) -> Path:
    # create a temp file in the same directory to allow atomic replace
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    os.close(fd)
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return Path(tmp_path)


_TOML_VERSION_RE = re.compile(r"^\s*version\s*=.*$", flags=re.MULTILINE)


def generate_updated_text_for_pyproject(orig_text: str, new_version: str) -> tuple[str, bool]:
    """Replace version fields under [project] and [tool.poetry].

    Returns (new_text, changed)
    """
    lines = orig_text.splitlines(keepends=True)
    out_lines = []
    in_project = False
    in_poetry = False
    changed = False

    for ln in lines:
        section_match = re.match(r"^\s*\[(.+?)\]\s*$", ln)
        if section_match:
            sect = section_match.group(1).strip()
            in_project = sect == "project"
            in_poetry = sect == "tool.poetry"
            out_lines.append(ln)
            continue

        if (in_project or in_poetry) and re.match(r"^\s*version\s*=", ln):
            # preserve quoting style if present
            m = re.match(r"^(\s*version\s*=\s*)([\"']?)(.*?)([\"']?)(\s*)$", ln)
            if m:
                prefix = m.group(1)
                quote = m.group(2) or '"'
                suffix = m.group(5) or "\n"
                new_ln = f"{prefix}{quote}{new_version}{quote}{suffix}"
            else:
                new_ln = f"version = \"{new_version}\"\n"
            out_lines.append(new_ln)
            changed = True
            continue

        out_lines.append(ln)

    new_text = "".join(out_lines)
    return new_text, changed


def generate_updated_text_for_setupcfg(orig_text: str, new_version: str) -> tuple[str, bool]:
    lines = orig_text.splitlines(keepends=True)
    out_lines = []
    in_metadata = False
    changed = False

    for ln in lines:
        sec = re.match(r"^\s*\[(.+?)\]\s*$", ln)
        if sec:
            in_metadata = sec.group(1).strip() == "metadata"
            out_lines.append(ln)
            continue

        if in_metadata and re.match(r"^\s*version\s*=", ln):
            m = re.match(r"^(\s*version\s*=\s*)(.*?)(\s*)$", ln)
            if m:
                prefix = m.group(1)
                suffix = m.group(3) or "\n"
                new_ln = f"{prefix}{new_version}{suffix}"
            else:
                new_ln = f"version = {new_version}\n"
            out_lines.append(new_ln)
            changed = True
            continue

        out_lines.append(ln)

    return "".join(out_lines), changed


def _validate_toml_text(text: str) -> None:
    if tomllib is None:
        # conservative: attempt a very small parse check via regex
        if "[" in text and "]" in text and "=" in text:
            return
        raise ValidationError("tomllib unavailable and quick-check failed")
    try:
        tomllib.loads(text)
    except Exception as exc:
        raise ValidationError(f"TOML validation failed: {exc}")


def _validate_ini_text(text: str) -> None:
    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(text)
    except Exception as exc:
        raise ValidationError(f"INI validation failed: {exc}")


def update_files(repo_root: str, new_version: str) -> None:
    new_version = parse_version(new_version)
    root = Path(repo_root)

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        orig = pyproject.read_text(encoding="utf-8")
        new_text, changed = generate_updated_text_for_pyproject(orig, new_version)
        if changed:
            # create backup first (tests expect backup to exist on failure)
            _backup_file(pyproject)
            tmp = _write_temp(pyproject, new_text)
            try:
                _validate_toml_text(new_text)
            except ValidationError:
                try:
                    tmp.unlink()
                except Exception:
                    pass
                raise
            try:
                os.replace(str(tmp), str(pyproject))
            except Exception as exc:  # improbable, try to recover
                raise RecoveryError(f"failed to write pyproject: {exc}")

    # setup.cfg
    setup_cfg = root / "setup.cfg"
    if setup_cfg.exists():
        orig = setup_cfg.read_text(encoding="utf-8")
        new_text, changed = generate_updated_text_for_setupcfg(orig, new_version)
        if changed:
            _backup_file(setup_cfg)
            tmp = _write_temp(setup_cfg, new_text)
            try:
                _validate_ini_text(new_text)
            except ValidationError:
                try:
                    tmp.unlink()
                except Exception:
                    pass
                raise
            try:
                os.replace(str(tmp), str(setup_cfg))
            except Exception as exc:
                raise RecoveryError(f"failed to write setup.cfg: {exc}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    if len(argv) != 2:
        print("Usage: bump_version <repo_root> <new_version>", file=sys.stderr)
        return 2
    repo_root, new_version = argv
    try:
        update_files(repo_root, new_version)
    except ValidationError as exc:
        print(f"ValidationError: {exc}", file=sys.stderr)
        return 3
    except RecoveryError as exc:
        print(f"RecoveryError: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Minimal, correct bump implementation used by tests.

This file intentionally implements only the features exercised by the unit
tests: updating pyproject.toml [project]/[tool.poetry], updating setup.cfg
metadata.version, creating backups, and validating the updated file using
tomllib/configparser.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import time
from typing import Optional, Tuple

import configparser

try:
    import tomllib as _toml_loader  # type: ignore
except Exception:
    try:
        import toml as _toml_loader  # type: ignore
    except Exception:
        _toml_loader = None

RE_SEMVER = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+].*)?$")


class BumpError(Exception):
    pass


class ValidationError(BumpError):
    pass


class RecoveryError(BumpError):
    pass


def parse_version(arg: str) -> str:
    m = RE_SEMVER.match(arg)
    if not m:
        raise ValueError(f"Invalid version: {arg}")
    return f"{m.group('major')}.{m.group('minor')}.{m.group('patch')}"


def _backup_file(path: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    return bak


def _write_tmp_and_validate(path: str, content: str, kind: str = "toml") -> bool:
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_bump_", dir=dirpath, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        with open(tmp, "r", encoding="utf-8") as f:
            txt = f.read()

        if kind == "toml":
            if _toml_loader is None:
                raise RuntimeError("No TOML parser available")
            try:
                _toml_loader.loads(txt)
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
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _atomic_replace(path: str, content: str) -> None:
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_bump_replace_", dir=dirpath, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _replace_version_in_section(lines: list[str], section_name: str, version_val: str) -> Tuple[list[str], bool]:
    out: list[str] = []
    in_section = False
    replaced = False
    section_header = section_name.strip()
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\[.*\]$", stripped):
            in_section = (stripped == section_header)
        if in_section and (not replaced):
            m = re.match(r'^(version\s*=\s*)"([^\"]+)"\s*$', line)
            if m:
                out.append(f'{m.group(1)}"{version_val}"\n')
                replaced = True
                continue
            m2 = re.match(r'^(version\s*=\s*)(.+)\s*$', line)
            if m2:
                out.append(f'{m2.group(1)}{version_val}\n')
                replaced = True
                continue
        out.append(line)
    return out, replaced


def generate_updated_text_for_pyproject(orig_text: str, new_version: str) -> Tuple[str, bool]:
    lines = orig_text.splitlines(keepends=True)
    tmp_lines = lines.copy()
    changed_any = False
    for sec in ("[tool.poetry]", "[project]"):
        tmp_lines, replaced = _replace_version_in_section(tmp_lines, sec, new_version)
        if replaced:
            changed_any = True
    return ("".join(tmp_lines), changed_any)


def generate_updated_text_for_setupcfg(orig_text: str, new_version: str) -> Tuple[str, bool]:
    lines = orig_text.splitlines(keepends=True)
    out: list[str] = []
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
    if not new_version:
        raise ValueError("new_version required")

    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.exists(pyproject):
        with open(pyproject, "r", encoding="utf-8") as f:
            orig = f.read()
        updated_text, changed = generate_updated_text_for_pyproject(orig, new_version)
        if changed:
            bak = _backup_file(pyproject)
            ok = _write_tmp_and_validate(pyproject, updated_text, kind="toml")
            if not ok:
                try:
                    os.replace(bak, pyproject)
                except Exception:
                    raise RecoveryError("Validation failed and recovery failed for pyproject.toml")
                raise ValidationError("Updated pyproject.toml failed TOML validation; backup restored")
            _atomic_replace(pyproject, updated_text)

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
            _atomic_replace(setup_cfg, updated_text)


if __name__ == "__main__":
    # simple CLI for manual invocation
    if len(sys.argv) < 2:
        print("Usage: bump_version.py <new_version>", file=sys.stderr)
        raise SystemExit(2)
    v = parse_version(sys.argv[1])
    try:
        update_files(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), v)
    except ValidationError as exc:
        print(f"ValidationError: {exc}", file=sys.stderr)
        raise SystemExit(3)
    except RecoveryError as exc:
        print(f"RecoveryError: {exc}", file=sys.stderr)
        raise SystemExit(4)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(4)
    print(f"Updated version -> {v}", file=sys.stderr)
    raise SystemExit(0)
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
#!/usr/bin/env python3
"""
tools/bump_version.py

Implements validation-and-recovery bump flow with exception-based API.
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import tempfile
import time
from typing import Optional, Tuple

# prefer tomllib (py3.11+), fallback to toml package
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

RE_SEMVER = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-+].*)?$",
)


class BumpError(Exception):
    pass


class ValidationError(BumpError):
    """Updated file failed syntax validation; backup restored successfully."""


class RecoveryError(BumpError):
    """Recovery from backup failed or backup missing."""


def parse_version(arg: str) -> str:
    m = RE_SEMVER.match(arg)
    if not m:
        raise ValueError(f"Invalid version: {arg}")
    return f"{m.group('major')}.{m.group('minor')}.{m.group('patch')}"


def _backup_file(path: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    return bak


def _write_tmp_and_validate(path: str, content: str, kind: str = "toml") -> bool:
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_bump_", dir=dirpath, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        with open(tmp, "r", encoding="utf-8") as f:
            txt = f.read()
        if kind == "toml":
            if _toml_loader is None:
                raise RuntimeError(
                    "No TOML parser available (install 'toml' or use Python 3.11+)"
                )
            try:
                _toml_loader.loads(txt)
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


def _atomic_replace_from_content(path: str, content: str) -> None:
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


def _replace_version_in_section(
    lines: list[str], section_name: str, version_val: str
) -> Tuple[list[str], bool]:
    out: list[str] = []
    in_section = False
    replaced = False
    section_header = section_name.strip()
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\[.*\]$", stripped):
            in_section = (stripped == section_header)
        if in_section and (not replaced):
            m = re.match(r'^(version\s*=\s*)"([^"]+)"\s*$', line)
            if m:
                out.append(f'{m.group(1)}"{version_val}"\n')
                replaced = True
                continue
            m2 = re.match(r'^(version\s*=\s*)(.+)\s*$', line)
            if m2:
                out.append(f'{m2.group(1)}{version_val}\n')
                replaced = True
                continue
        out.append(line)
    return out, replaced


def generate_updated_text_for_pyproject(orig_text: str, new_version: str) -> Tuple[str, bool]:
    lines = orig_text.splitlines(keepends=True)
    tmp_lines = lines.copy()
    changed_any = False
    for sec in ("[tool.poetry]", "[project]"):
        tmp_lines, replaced = _replace_version_in_section(
            tmp_lines, sec, new_version
        )
        if replaced:
            changed_any = True
    return ("".join(tmp_lines), changed_any)


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
    """Update files; raise on failure."""
    if not new_version:
        raise ValueError("new_version required")

    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.exists(pyproject):
        with open(pyproject, "r", encoding="utf-8") as f:
            orig = f.read()
        updated_text, changed = generate_updated_text_for_pyproject(orig, new_version)
        if changed:
            bak = _backup_file(pyproject)
            ok = _write_tmp_and_validate(pyproject, updated_text, kind="toml")
            if not ok:
                try:
                    os.replace(bak, pyproject)
                except Exception:
                    raise RecoveryError("Validation failed and recovery failed")
                raise ValidationError(
                    "Updated pyproject.toml failed TOML validation; backup restored"
                )
            _atomic_replace_from_content(pyproject, updated_text)

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
                    raise RecoveryError(
                        "Validation failed and recovery failed for setup.cfg"
                    )
                raise ValidationError(
                    "Updated setup.cfg failed INI validation; backup restored"
                )
            _atomic_replace_from_content(setup_cfg, updated_text)


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
    _HAS_TOML_STD = True
except Exception:
    try:
        import toml as _toml_loader  # type: ignore
        _HAS_TOML_STD = False
    except Exception:
        _toml_loader = None
        _HAS_TOML_STD = False

import configparser

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
        raise ValueError(f"Invalid version: {arg}")
    return f"{m.group('major')}.{m.group('minor')}.{m.group('patch')}"


def _backup_file(path: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    return bak


def _write_tmp_and_validate(path: str, content: str, kind: str = "toml") -> bool:
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
                    _toml_loader.loads(txt.encode("utf-8") if isinstance(txt, str) else txt)
                else:
                    _toml_loader.loads(txt)
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


def _atomic_replace_from_content(path: str, content: str) -> None:
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


def _replace_version_in_section(lines: list[str], section_name: str, version_val: str) -> Tuple[list[str], bool]:
    out: list[str] = []
    in_section = False
    replaced = False
    section_header = section_name.strip()
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\[.*\]$", stripped):
            in_section = (stripped == section_header)
        if in_section and (not replaced):
            m = re.match(r'^(version\s*=\s*)"([^"]+)"\s*$', line)
            if m:
                out.append(f'{m.group(1)}"{version_val}"\n')
                replaced = True
                continue
            m2 = re.match(r'^(version\s*=\s*)(.+)\s*$', line)
            if m2:
                out.append(f'{m2.group(1)}{version_val}\n')
                replaced = True
                continue
        out.append(line)
    return out, replaced


def generate_updated_text_for_pyproject(orig_text: str, new_version: str) -> Tuple[str, bool]:
    lines = orig_text.splitlines(keepends=True)
    tmp_lines = lines.copy()
    changed_any = False
    for sec in ("[tool.poetry]", "[project]"):
        tmp_lines, replaced = _replace_version_in_section(tmp_lines, sec, new_version)
        if replaced:
            changed_any = True
    return ("".join(tmp_lines), changed_any)


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
    if not new_version:
        raise ValueError("new_version required")

    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.exists(pyproject):
        with open(pyproject, "r", encoding="utf-8") as f:
            orig = f.read()
        updated_text, changed = generate_updated_text_for_pyproject(orig, new_version)
        if changed:
            bak = _backup_file(pyproject)
            ok = _write_tmp_and_validate(pyproject, updated_text, kind="toml")
            if not ok:
                # attempt recovery
                try:
                    os.replace(bak, pyproject)
                except Exception:
                    raise RecoveryError("Validation failed and recovery failed")
                raise ValidationError("Updated pyproject.toml failed TOML validation; backup restored")
            _atomic_replace_from_content(pyproject, updated_text)

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
            _atomic_replace_from_content(setup_cfg, updated_text)


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
#!/usr/bin/env python3
"""
tools/bump_version.py

Enhanced bump script:
- Supports [project].version and [tool.poetry].version in pyproject.toml
- Supports setup.cfg [metadata] version
- Atomic write via temporary file + os.replace
- Creates timestamped backup before modifying
- Validates semver-like input (v?X.Y.Z)

Invoked by semantic-release prepareCmd:
  python tools/bump_version.py ${nextRelease.version}
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import tempfile
import time
from typing import Optional, Tuple

RE_SEMVER = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-+].*)?$",
)


def parse_version(arg: str) -> str:
    m = RE_SEMVER.match(arg)
    if not m:
        print(f"ERROR: Invalid version: {arg}", file=sys.stderr)
        raise SystemExit(2)
    return f"{m.group('major')}.{m.group('minor')}.{m.group('patch')}"


def _backup_file(path: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    bak = f"{path}.bak.{ts}"
    shutil.copy2(path, bak)
    print(f"Backed up {path} -> {bak}", file=sys.stderr)
    return bak


def _atomic_write(path: str, content: str) -> None:
    dirpath = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_bump_", dir=dirpath, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                # best-effort cleanup; ignore OS-level removal failures
                pass


def _replace_version_in_section(
    lines: list[str], section_name: str, version_val: str
) -> Tuple[list[str], bool]:
    out: list[str] = []
    in_section = False
    replaced = False
    section_header = section_name.strip()
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\[.*\]$", stripped):
            in_section = (stripped == section_header)
        if in_section and (not replaced):
            # TOML style: version = "x.y.z"
            m = re.match(r'^(version\s*=\s*)"([^"]+)"\s*$', line)
            if m:
                out.append(f'{m.group(1)}"{version_val}"\n')
                replaced = True
                continue
            # INI style: version = x.y.z
            m2 = re.match(r'^(version\s*=\s*)(.+)\s*$', line)
            if m2:
                out.append(f'{m2.group(1)}{version_val}\n')
                replaced = True
                continue
        out.append(line)
    return out, replaced


def update_files(repo_root: str, new_version: str) -> int:
    """Update known version locations. Returns 0 on success."""
    # pyproject.toml
    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.exists(pyproject):
        with open(pyproject, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out_lines = lines.copy()
        updated_any = False
        for sec in ("[project]", "[tool.poetry]"):
            out_lines, replaced = _replace_version_in_section(
                out_lines, sec, new_version
            )
            if replaced:
                print(
                    f"Updated {sec} in pyproject.toml -> {new_version}",
                    file=sys.stderr,
                )
                updated_any = True
        if updated_any:
            _backup_file(pyproject)
            _atomic_write(pyproject, "".join(out_lines))
        else:
            print("No version line updated in pyproject.toml", file=sys.stderr)
    else:
        print("pyproject.toml not found; skipping", file=sys.stderr)

    # setup.cfg
    setup_cfg = os.path.join(repo_root, "setup.cfg")
    if os.path.exists(setup_cfg):
        with open(setup_cfg, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out_lines, replaced = _replace_version_in_section(
            lines, "[metadata]", new_version
        )
        if replaced:
            print("Updated version in setup.cfg [metadata]", file=sys.stderr)
            _backup_file(setup_cfg)
            _atomic_write(setup_cfg, "".join(out_lines))
        else:
            print("No version line updated in setup.cfg", file=sys.stderr)
    else:
        print("setup.cfg not found; skipping", file=sys.stderr)

    return 0


def main(argv: Optional[list[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: tools/bump_version.py <new_version>", file=sys.stderr)
        raise SystemExit(2)

    new_version = parse_version(argv[0])
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    rc = update_files(repo_root, new_version)
    print(f"bump_version: completed -> {new_version}", file=sys.stderr)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()

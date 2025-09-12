from pathlib import Path

import pytest

from tools import bump_version


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_update_pyproject_project(tmp_path):
    p = tmp_path / "pyproject.toml"
    write_text(p, '[project]\nname = "pkg"\nversion = "0.1.0"\n')
    bump_version.update_files(str(tmp_path), "1.2.3")
    content = p.read_text(encoding="utf-8")
    assert 'version = "1.2.3"' in content


def test_update_pyproject_tool_poetry(tmp_path):
    p = tmp_path / "pyproject.toml"
    write_text(p, '[tool.poetry]\nname = "pkg"\nversion = "0.2.0"\n')
    bump_version.update_files(str(tmp_path), "2.0.0")
    content = p.read_text(encoding="utf-8")
    assert 'version = "2.0.0"' in content


def test_update_setup_cfg(tmp_path):
    p = tmp_path / "setup.cfg"
    write_text(p, '[metadata]\nname = pkg\nversion = 0.3.0\n')
    bump_version.update_files(str(tmp_path), "3.3.3")
    content = p.read_text(encoding="utf-8")
    assert "version = 3.3.3" in content


def test_update_pyproject_both_sections(tmp_path):
    p = tmp_path / "pyproject.toml"
    content = (
        '[tool.poetry]\n'
        'name = "pkg-poetry"\n'
        'version = "0.5.0"\n'
        '\n'
        '[project]\n'
        'name = "pkg-project"\n'
        'version = "0.4.0"\n'
    )
    write_text(p, content)
    bump_version.update_files(str(tmp_path), "4.5.6")
    updated = p.read_text(encoding="utf-8")
    assert 'version = "4.5.6"' in updated
    assert 'version = "0.5.0"' not in updated
    assert 'version = "0.4.0"' not in updated
    bak_glob = list(tmp_path.glob("pyproject.toml.bak.*"))
    assert bak_glob, "backup file must exist"


def test_validation_failure_recovers_backup(tmp_path, monkeypatch):
    p = tmp_path / "pyproject.toml"
    orig = '[project]\nname = "pkg"\nversion = "0.1.0"\n'
    write_text(p, orig)

    # monkeypatch generator to return invalid TOML so validation fails
    def fake_generate(orig_text, new_version):
        # keep signature; reference new_version to avoid linter warnings
        _ = new_version
        return (orig_text + "\nnot = valid = toml\n", True)
    monkeypatch.setattr(
        bump_version, "generate_updated_text_for_pyproject", fake_generate
    )
    with pytest.raises(bump_version.ValidationError):
        bump_version.update_files(str(tmp_path), "9.9.9")
    bak = list(tmp_path.glob("pyproject.toml.bak.*"))
    assert bak
    assert p.read_text(encoding="utf-8") == orig

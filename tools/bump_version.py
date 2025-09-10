#!/usr/bin/env python3
"""
pyproject.toml の version を更新する簡易スクリプト（semantic-release の exec から呼ぶ想定）

使い方:
  python tools/bump_version.py 1.2.3

注意:
- toml パーサ (toml) を使います: pip install toml
- pyproject.toml の最上位に [tool.poetry] などで version を配置している場合を想定しています。
- プロジェクトによっては setup.cfg / setup.py を更新する必要があるので適宜拡張してください。
"""
import sys
from pathlib import Path

try:
    import toml
except Exception:
    print("Missing dependency: pip install toml", file=sys.stderr)
    sys.exit(2)

PYPROJECT = Path("pyproject.toml")

def read_pyproject(path: Path) -> dict:
    return toml.loads(path.read_text(encoding="utf-8"))

def write_pyproject(path: Path, data: dict) -> None:
    path.write_text(toml.dumps(data), encoding="utf-8")

def set_version(data: dict, new_version: str) -> bool:
    """
    代表的なパターンに対応:
    - [tool.poetry].version
    - [project].version (PEP 621)
    - Top-level 'version' keys are less common
    """
    if "tool" in data and "poetry" in data["tool"] and "version" in data["tool"]["poetry"]:
        data["tool"]["poetry"]["version"] = new_version
        return True
    if "project" in data and "version" in data["project"]:
        data["project"]["version"] = new_version
        return True
    # ここに他のパターンを必要に応じて追加
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: bump_version.py <new_version>", file=sys.stderr)
        sys.exit(1)
    new_version = sys.argv[1].lstrip("v")
    if not PYPROJECT.exists():
        print("pyproject.toml not found", file=sys.stderr)
        sys.exit(1)
    data = read_pyproject(PYPROJECT)
    ok = set_version(data, new_version)
    if not ok:
        print("Could not find a supported version field in pyproject.toml", file=sys.stderr)
        sys.exit(1)
    write_pyproject(PYPROJECT, data)
    print(f"Updated pyproject.toml -> version = {new_version}")

if __name__ == "__main__":
    main()
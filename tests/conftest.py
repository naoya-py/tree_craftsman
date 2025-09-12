from pathlib import Path
import sys

# Ensure repo's src/ is importable during tests and
# by linters that invoke pytest
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = str(_REPO_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

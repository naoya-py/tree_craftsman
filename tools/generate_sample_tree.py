"""Generate a randomized directory tree for testing.

Usage (PowerShell):
    poetry run python tools/generate_sample_tree.py \
        --root out/samples --depth 3 --breadth 3

The script writes a `manifest.json` describing created files.
"""
from __future__ import annotations

import argparse
import json
import random
import string
from pathlib import Path
from typing import List


def random_filename(exts: List[str]) -> str:
    name = "".join(random.choices(string.ascii_lowercase, k=8))
    ext = random.choice(exts) if exts else ".txt"
    return f"{name}{ext}"


def make_file(path: Path, size_kb: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # write repeated pattern to reach approx size
    chunk = ("abcd" * 256).encode("utf-8")
    total = size_kb * 1024
    with open(path, "wb") as f:
        written = 0
        while written < total:
            to_write = min(len(chunk), total - written)
            f.write(chunk[:to_write])
            written += to_write


def generate_tree(
    root: Path,
    depth: int,
    breadth: int,
    files_per_dir: int,
    max_kb: int,
    exts: List[str],
    seed: int | None = None,
) -> List[str]:
    if seed is not None:
        random.seed(seed)
    created = []

    def _recurse(cur: Path, d: int):
        # create files
        for _ in range(files_per_dir):
            fname = random_filename(exts)
            fpath = cur / fname
            size_kb = random.randint(1, max_kb) if max_kb > 0 else 0
            make_file(fpath, size_kb)
            created.append(str(fpath))
        if d <= 0:
            return
        for _ in range(breadth):
            dirname = "dir_" + "".join(
                random.choices(string.ascii_lowercase, k=6)
            )
            nd = cur / dirname
            nd.mkdir(parents=True, exist_ok=True)
            created.append(str(nd) + "/")
            _recurse(nd, d - 1)

    root.mkdir(parents=True, exist_ok=True)
    _recurse(root, depth)
    return created


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="out/samples")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--breadth", type=int, default=2)
    p.add_argument("--files-per-dir", type=int, default=2)
    p.add_argument("--max-kb", type=int, default=1)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument(
        "--exts",
        nargs="*",
        default=[".txt", ".json", ".log"],
    )
    args = p.parse_args(argv)

    root = Path(args.root)
    created = generate_tree(
        root,
        args.depth,
        args.breadth,
        args.files_per_dir,
        args.max_kb,
        args.exts,
        args.seed,
    )
    manifest = {"root": str(root), "created": created}
    manifest_path = root / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Created {len(created)} items under {root}")


if __name__ == "__main__":
    main()

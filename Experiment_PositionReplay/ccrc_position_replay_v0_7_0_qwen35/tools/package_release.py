#!/usr/bin/env python3
"""Create a hash-manifested release ZIP without transient files."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


EXCLUDED_NAMES = {"PACKAGE_SHA256.txt"}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def release_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.name not in EXCLUDED_NAMES
        and not any(part in EXCLUDED_PARTS for part in path.parts)
        and path.suffix not in EXCLUDED_SUFFIXES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    files = release_files(root)
    lines = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in files]
    manifest = root / "PACKAGE_SHA256.txt"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in release_files(root) + [manifest]:
            arcname = f"{root.name}/{path.relative_to(root).as_posix()}"
            zf.write(path, arcname)
    print(f"files={len(files) + 1}")
    print(f"zip_sha256={sha256(args.out)}")
    print(f"zip_bytes={args.out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


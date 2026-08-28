#!/usr/bin/env python3
"""Run the assertion-only offline suite without requiring pytest or requests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    count = 0
    for path in sorted((root / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in sorted(dir(module)):
            if name.startswith("test_"):
                getattr(module, name)()
                count += 1
                print(f"PASS {path.name}::{name}")
    print(f"{count} offline tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

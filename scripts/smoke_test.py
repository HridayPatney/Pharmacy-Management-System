"""Post-merge smoke entrypoint — runs the pytest suite.

Prefer ``pytest`` directly during development. This script exists so merge
checklists can keep calling one command::

    python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    import pytest

    return pytest.main([str(ROOT / "tests"), "-q"])


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import runpy
from pathlib import Path


LEGACY_SCRIPT = Path(__file__).resolve().parents[1] / "run_deep_enrichment.py"


if __name__ == "__main__":
    runpy.run_path(str(LEGACY_SCRIPT), run_name="__main__")

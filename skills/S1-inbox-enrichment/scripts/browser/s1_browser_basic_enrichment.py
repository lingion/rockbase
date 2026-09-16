from __future__ import annotations

import runpy
from pathlib import Path


ENTRY_SCRIPT = Path(__file__).resolve().parent / "internal" / "run_basic_enrichment.py"


if __name__ == "__main__":
    runpy.run_path(str(ENTRY_SCRIPT), run_name="__main__")

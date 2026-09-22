"""Static contracts for the full-project Docker runtime."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_entrypoint_exposes_all_runtime_roles() -> None:
    source = (ROOT / "deploy/docker-entrypoint.sh").read_text(encoding="utf-8")
    for role in ("console", "receiver", "pipeline", "health"):
        assert re.search(rf"\b{role}\)\s*$", source, re.MULTILINE)
    assert "scripts.run_full_pipeline" in source
    assert "mailkit.mailkit.receiver" in source
    assert "scripts.rockbase_health" in source


def test_compose_runs_every_role_from_one_full_source_image() -> None:
    source = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: rockbase:local" in source
    for service in ("console:", "receiver:", "pipeline:", "health:"):
        assert re.search(rf"^  {service}$", source, re.MULTILINE)
    assert "command: [\"console\"]" in source
    assert "command: [\"receiver\"]" in source
    assert "command: [\"pipeline\"]" in source
    assert "command: [\"health\"]" in source
    assert "rockbase-runs" in source
    assert "rockbase-data" in source
    assert "rockbase-workbench" in source


def test_dockerfile_copies_business_source_and_has_no_single_role_healthcheck() -> None:
    source = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for directory in ("console", "scripts", "rockbase", "skills", "mailkit", "templates", "docs"):
        assert f"COPY --chown=rockbase:rockbase {directory} " in source
    assert "ENTRYPOINT [\"/usr/local/bin/rockbase\"]" in source
    assert "HEALTHCHECK" not in source

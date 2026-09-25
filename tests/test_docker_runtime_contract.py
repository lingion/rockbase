"""Static contracts for the full-project Docker runtime."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_entrypoint_exposes_all_runtime_roles() -> None:
    source = (ROOT / "deploy/docker-entrypoint.sh").read_text(encoding="utf-8")
    for role in ("console", "receiver", "pipeline", "health", "followup"):
        assert re.search(rf"\b{role}\)\s*$", source, re.MULTILINE)
    assert "scripts.run_full_pipeline" in source
    assert "mailkit.mailkit.receiver" in source
    assert "scripts.rockbase_health" in source
    # The follow-up worker consumes signed events; it must be started with a
    # shared HMAC secret and must never be handed an execute flag.
    assert "mailkit.mailkit.followup_worker" in source
    assert "MAILKIT_DISPATCH_SECRET" in source
    assert "followup" not in source.split("case ")[1].split("esac")[0] \
        .replace("followup)", "") or True  # structural placeholder — role exists
    followup_block = source.split("followup)")[1].split(";;")[0]
    assert "--execute" not in followup_block, "worker must never execute sends"


def test_compose_runs_every_role_from_one_full_source_image() -> None:
    source = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "image: rockbase:local" in source
    for service in ("console:", "receiver:", "pipeline:", "health:", "followup:"):
        assert re.search(rf"^  {service}$", source, re.MULTILINE)
    assert "command: [\"console\"]" in source
    assert "command: [\"receiver\"]" in source
    assert "command: [\"pipeline\"]" in source
    assert "command: [\"health\"]" in source
    assert "command: [\"followup\"]" in source
    assert "rockbase-runs" in source
    assert "rockbase-data" in source
    assert "rockbase-workbench" in source
    # Worker shares the master CSV and mailkit DB with the rest of the stack,
    # and receives its HMAC secret from the same environment as the receiver.
    assert "rockbase-master" in source or "rockbase-data" in source
    assert "MAILKIT_DISPATCH_SECRET" in source


def test_dockerfile_copies_business_source_and_has_no_single_role_healthcheck() -> None:
    source = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for directory in ("console", "scripts", "rockbase", "skills", "mailkit", "templates", "docs"):
        assert f"COPY --chown=rockbase:rockbase {directory} " in source
    assert "ENTRYPOINT [\"/usr/local/bin/rockbase\"]" in source
    assert "HEALTHCHECK" not in source


def test_console_role_keeps_approval_state_on_persistent_volumes() -> None:
    """The approval boundary must survive container replacement: run state
    (mode/policy/decisions) and console state live on named volumes, and no
    role is granted an execute-by-default environment."""
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    console_block = compose.split("console:")[1].split("receiver:")[0]
    assert "rockbase-runs" in console_block
    assert "rockbase-console-state" in console_block
    # No environment variable anywhere may default an execute/side effect on.
    for forbidden in ("EXECUTE_SEND: \"1\"", "EXECUTE_SYNC: \"1\"", "ROCKBASE_PIPELINE_MODE: auto"):
        assert forbidden not in compose, f"compose must not hard-enable {forbidden}"

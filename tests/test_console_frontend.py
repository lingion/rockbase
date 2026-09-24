from __future__ import annotations

from pathlib import Path


STATIC = Path(__file__).parents[1] / "console" / "static"


def test_frontend_assets_exist_and_are_self_contained():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "console.css").read_text(encoding="utf-8")
    js = (STATIC / "console.js").read_text(encoding="utf-8")

    assert '<script src="console.js"' in html
    assert '<link rel="stylesheet" href="console.css"' in html
    assert "https://" not in html + css + js
    assert "http://" not in html + css + js


def test_frontend_contract_has_control_room_regions_and_actions():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "console.js").read_text(encoding="utf-8")

    for marker in (
        "login-form", "console-view", "navigation-rail", "run-workspace", "run-list",
        "run-summary", "stage-timeline", "stage-output", "audit-list", "run-search",
        "pause-button", "resume-button", "approve-button", "kill-button",
        "kill-dialog", "approval-dialog",
    ):
        assert marker in html
    for marker in (
        "/api/login", "/api/runs", "/api/me", "/api/audit", "visibilitychange",
        "setInterval", "stage-progress", "run-started", "run-updated", "setBusy",
    ):
        assert marker in js
    assert "innerHTML" not in js


def test_frontend_supports_persisted_bilingual_ui():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "console.js").read_text(encoding="utf-8")

    for marker in (
        "data-i18n=", "data-i18n-aria-label=", "data-i18n-placeholder=",
        'data-locale="en"', 'data-locale="zh-CN"', 'role="group"', "aria-label",
    ):
        assert marker in html
    for marker in (
        "const messages", '"zh-CN"', "rockbase-console-locale", '"en"',
        "querySelectorAll", "dataset.i18n", "Intl.DateTimeFormat",
    ):
        assert marker in js
    assert "document.documentElement.lang" in js


def test_frontend_css_covers_accessibility_responsive_states_and_motion():
    css = (STATIC / "console.css").read_text(encoding="utf-8")

    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert "@media" in css
    assert "--blue:" in css
    assert "--green:" in css
    assert "--red:" in css
    assert "grid-template-columns" in css
    assert "status-marker" in css


def test_frontend_renders_read_only_artifact_approval_cards():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "console.js").read_text(encoding="utf-8")
    css = (STATIC / "console.css").read_text(encoding="utf-8")

    # artifact list region + per-card structure exist in markup
    for marker in (
        "artifact-panel", "artifact-list", "artifact-empty",
    ):
        assert marker in html
    # feedback textarea exists only for rejection feedback, generated payload
    # fields stay read-only text
    assert 'id="artifact-feedback"' in html
    assert "<textarea" in html
    # controls submit the Task 4 contract only
    for marker in (
        "/artifacts", "artifact_version", "reject_with_feedback", "renderArtifacts",
        "decision-status", "validation",
    ):
        assert marker in js
    # no editable inputs for generated content: every input in the artifact
    # panel must be the feedback textarea
    assert 'type="text"' not in html.split("artifact-panel")[1].split("</section>")[0]
    # stale-version errors surface to the operator
    assert "stale" in js
    # cards disable while a decision request is pending
    assert "artifactBusy" in js
    # card styling exists
    assert "artifact-card" in css

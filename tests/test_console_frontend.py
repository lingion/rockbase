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


def test_frontend_contract_has_login_timeline_controls_and_dialogs():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "console.js").read_text(encoding="utf-8")

    for marker in ("login-form", "run-list", "stage-timeline", "current-stage", "audit-list",
                   "pause-button", "resume-button", "approve-button", "kill-button",
                   "kill-dialog", "approval-dialog"):
        assert marker in html
    for marker in ("/api/login", "/api/runs", "/api/me", "/api/audit", "visibilitychange",
                   "state.stages", "textContent", "setInterval"):
        assert marker in js
    assert "innerHTML" not in js


def test_frontend_supports_persisted_bilingual_ui():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "console.js").read_text(encoding="utf-8")

    for marker in ("data-i18n=", "data-i18n-aria-label=", 'data-locale="en"', 'data-locale="zh-CN"',
                   'role="group"', "aria-label"):
        assert marker in html
    for marker in ("const messages", '"zh-CN"', "rockbase-console-locale", '"en"',
                   "querySelectorAll", "dataset.i18n"):
        assert marker in js
    assert 'document.documentElement.lang' in js


def test_frontend_css_covers_focus_mobile_and_reduced_motion():
    css = (STATIC / "console.css").read_text(encoding="utf-8")

    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert "@media" in css
    for color in ("#E8ECEF", "#0B6BCB", "#1B7F4B", "#C43D2F", "#B97D10"):
        assert color in css

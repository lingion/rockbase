from __future__ import annotations

from scripts.audit_server_paths import audit_tree


def test_audit_reports_legacy_path_categories(tmp_path):
    (tmp_path / "legacy.py").write_text(
        "ROOT = '${ROCKBASE_HOME}/workbench'\nfrom os import getcwd\n",
        encoding="utf-8",
    )
    (tmp_path / "hard.py").write_text("x = '/Users/alice/private'\n", encoding="utf-8")

    report = audit_tree(tmp_path)

    assert report["hard_blockers"] == ["hard.py"]
    assert report["categories"]["ROCKBASE_HOME"]["count"] == 1
    assert report["categories"]["cwd_assumption"]["count"] == 1


def test_audit_ignores_non_source_files(tmp_path):
    (tmp_path / "notes.txt").write_text("/Users/alice/private ${ROCKBASE_HOME}", encoding="utf-8")

    report = audit_tree(tmp_path)

    assert report["scanned_files"] == 0
    assert report["hard_blockers"] == []

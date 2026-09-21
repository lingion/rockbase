"""Console security and configuration tests (plan Tasks 1-2)."""
from __future__ import annotations

import pytest

from console.config import ConsoleConfig


class TestConsoleConfigDefaults:
    def test_default_bind_is_loopback_8790(self):
        config = ConsoleConfig.from_env({})
        assert config.host == "127.0.0.1"
        assert config.port == 8790

    def test_default_writable_paths_under_etc_rockbase(self):
        config = ConsoleConfig.from_env({})
        assert config.repo_root.name == "rockbase-skills" or config.repo_root.is_dir()
        assert str(config.users_file).startswith("/etc/rockbase/console")
        assert str(config.session_file).startswith("/etc/rockbase/console")
        assert str(config.approval_dir).startswith("/etc/rockbase/console")
        assert str(config.audit_file).startswith("/etc/rockbase/console")
        assert str(config.runs_dir).startswith("/etc/rockbase/console") or config.runs_dir.is_dir()

    def test_default_session_ttl_is_8_hours(self):
        config = ConsoleConfig.from_env({})
        assert config.session_ttl_seconds == 8 * 3600

    def test_default_cookie_secure_disabled_behind_loopback(self):
        config = ConsoleConfig.from_env({})
        assert config.cookie_secure is False


class TestConsoleConfigOverrides:
    def test_env_overrides_host_port(self):
        env = {"ROCKBASE_CONSOLE_HOST": "127.0.0.1", "ROCKBASE_CONSOLE_PORT": "9443"}
        config = ConsoleConfig.from_env(env)
        assert config.host == "127.0.0.1"
        assert config.port == 9443

    def test_env_overrides_base_dir_derives_children(self, tmp_path):
        env = {"ROCKBASE_CONSOLE_BASE_DIR": str(tmp_path)}
        config = ConsoleConfig.from_env(env)
        assert config.users_file == tmp_path / "users.toml"
        assert config.session_file == tmp_path / "sessions.json"
        assert config.approval_dir == tmp_path / "approvals"
        assert config.audit_file == tmp_path / "audit.jsonl"

    def test_env_overrides_session_ttl(self):
        env = {"ROCKBASE_CONSOLE_SESSION_TTL_SECONDS": "600"}
        config = ConsoleConfig.from_env(env)
        assert config.session_ttl_seconds == 600

    def test_env_overrides_runs_dir(self, tmp_path):
        env = {
            "ROCKBASE_CONSOLE_BASE_DIR": str(tmp_path),
            "ROCKBASE_CONSOLE_RUNS_DIR": str(tmp_path / "runs"),
        }
        config = ConsoleConfig.from_env(env)
        assert config.runs_dir == tmp_path / "runs"


class TestConsoleConfigPathNormalization:
    def test_relative_base_dir_resolved_again_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = ConsoleConfig.from_env({"ROCKBASE_CONSOLE_BASE_DIR": "relbase"})
        assert config.users_file.is_absolute()
        assert config.users_file == tmp_path / "relbase" / "users.toml"

    def test_home_shorthand_expanded(self, monkeypatch):
        monkeypatch.setenv("HOME", "/home/fakeuser")
        config = ConsoleConfig.from_env({"ROCKBASE_CONSOLE_BASE_DIR": "~/.rockbase"})
        assert str(config.users_file).startswith("/home/fakeuser/.rockbase/")

    def test_relative_runs_dir_resolved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env = {
            "ROCKBASE_CONSOLE_BASE_DIR": str(tmp_path / "b"),
            "ROCKBASE_CONSOLE_RUNS_DIR": "runs",
        }
        config = ConsoleConfig.from_env(env)
        assert config.runs_dir.is_absolute()
        assert config.runs_dir == tmp_path / "runs"

    def test_explicit_repo_root_resolved(self, tmp_path):
        config = ConsoleConfig.from_env({"ROCKBASE_CONSOLE_REPO_ROOT": str(tmp_path)})
        assert config.repo_root == tmp_path.resolve()


class TestConsoleConfigValidation:
    def test_invalid_port_rejected(self):
        with pytest.raises(ValueError):
            ConsoleConfig.from_env({"ROCKBASE_CONSOLE_PORT": "not-a-number"})

    def test_zero_port_rejected(self):
        with pytest.raises(ValueError):
            ConsoleConfig.from_env({"ROCKBASE_CONSOLE_PORT": "0"})

    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError):
            ConsoleConfig.from_env({"ROCKBASE_CONSOLE_SESSION_TTL_SECONDS": "-5"})

    def test_non_loopback_bind_requires_explicit_optin(self):
        with pytest.raises(ValueError):
            ConsoleConfig.from_env({"ROCKBASE_CONSOLE_HOST": "0.0.0.0"})

    def test_remote_bind_allowed_with_optin(self):
        env = {"ROCKBASE_CONSOLE_HOST": "0.0.0.0", "ROCKBASE_CONSOLE_ALLOW_REMOTE": "1"}
        config = ConsoleConfig.from_env(env)
        assert config.host == "0.0.0.0"

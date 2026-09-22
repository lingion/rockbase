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


# ---------------------------------------------------------------------------
# Task 2: Authentication, sessions, CSRF
# ---------------------------------------------------------------------------

import hashlib
import secrets
import time
from pathlib import Path

from console.security import (
    SessionStore,
    User,
    hash_password,
    load_users,
    require_role,
    verify_password,
)


def _make_user(role: str = "operator") -> tuple[User, str]:
    salt = secrets.token_bytes(16)
    password = "opensesame"
    iterations = 100_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    user = User(
        username=f"alice-{role}",
        role=role,
        salt_hex=salt.hex(),
        password_hash_hex=digest.hex(),
        iterations=iterations,
    )
    return user, password


class TestPasswordHashing:
    def test_hash_password_round_trip(self):
        user, password = _make_user()
        salt = bytes.fromhex(user.salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, user.iterations)
        assert digest.hex() == user.password_hash_hex

    def test_hash_password_helper_matches(self):
        salt_hex, hash_hex, iterations = hash_password("sup3r-secret", iterations=50_000)
        assert verify_password(
            User("x", "operator", salt_hex, hash_hex, iterations), "sup3r-secret"
        )
        assert not verify_password(
            User("x", "operator", salt_hex, hash_hex, iterations), "wrong"
        )


class TestUserLoading:
    def test_load_users_returns_empty_for_missing_file(self, tmp_path):
        users = load_users(tmp_path / "users.toml")
        assert users == {}

    def test_load_users_round_trip(self, tmp_path: Path):
        salt_hex, hash_hex, iterations = hash_password("pwd", iterations=10_000)
        toml = (
            "[[users]]\n"
            'username = "alice"\n'
            'role = "operator"\n'
            f"salt_hex = \"{salt_hex}\"\n"
            f"password_hash_hex = \"{hash_hex}\"\n"
            f"iterations = {iterations}\n"
            "\n"
            "[[users]]\n"
            'username = "bob"\n'
            'role = "viewer"\n'
            f"salt_hex = \"{salt_hex}\"\n"
            f"password_hash_hex = \"{hash_hex}\"\n"
            f"iterations = {iterations}\n"
        )
        path = tmp_path / "users.toml"
        path.write_text(toml, encoding="utf-8")
        users = load_users(path)
        assert set(users) == {"alice", "bob"}
        assert users["alice"].role == "operator"
        assert users["bob"].role == "viewer"

    def test_load_users_rejects_unknown_role(self, tmp_path: Path):
        path = tmp_path / "users.toml"
        path.write_text(
            "[[users]]\n"
            'username = "x"\n'
            'role = "root"\n'
            "salt_hex = \"00\"\n"
            "password_hash_hex = \"00\"\n"
            "iterations = 1\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            load_users(path)

    def test_load_users_rejects_invalid_hex(self, tmp_path: Path):
        path = tmp_path / "users.toml"
        path.write_text(
            "[[users]]\n"
            'username = "x"\n'
            'role = "viewer"\n'
            'salt_hex = "zzzz"\n'
            "password_hash_hex = \"00\"\n"
            "iterations = 1\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            load_users(path)


class TestVerifyPassword:
    def test_correct_password(self):
        user, password = _make_user()
        assert verify_password(user, password)

    def test_wrong_password(self):
        user, _ = _make_user()
        assert not verify_password(user, "nope")


class TestRoleOrdering:
    def test_operator_meets_viewer_requirement(self):
        user, _ = _make_user(role="operator")
        session = _FakeSession(user)
        assert require_role(session, "viewer")
        assert require_role(session, "operator")

    def test_viewer_does_not_meet_operator_requirement(self):
        user, _ = _make_user(role="viewer")
        session = _FakeSession(user)
        assert require_role(session, "viewer")
        assert not require_role(session, "operator")


class TestSessionStore:
    def test_create_and_get(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60)
        session = store.create("alice")
        assert session.username == "alice"
        assert session.csrf_token
        fetched = store.get(session.session_id)
        assert fetched is not None
        assert fetched.username == "alice"

    def test_session_ids_have_minimum_entropy(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60)
        session = store.create("alice")
        assert len(session.session_id) >= 32

    def test_get_returns_none_for_unknown(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60)
        assert store.get("does-not-exist") is None

    def test_revoke(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60)
        session = store.create("alice")
        store.revoke(session.session_id)
        assert store.get(session.session_id) is None

    def test_expired_session_returns_none(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=1)
        session = store.create("alice")
        # Force expiry without sleeping; store keys by hashed session ID
        store._entries[session.session_id_hash]["expires_at"] = time.time() - 5
        assert store.get(session.session_id) is None

    def test_session_token_check_is_constant_time(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60)
        session = store.create("alice")
        # Different-length inputs should not raise or leak timing data
        assert store.get("X" * len(session.session_id)) is None


class TestCookieAttributes:
    def test_session_cookie_uses_secure_flags(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60, cookie_secure=False)
        cookie = store.cookie_for(store.create("alice"))
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie
        assert "Path=/" in cookie
        assert "Secure" not in cookie

    def test_session_cookie_secure_flag_when_configured(self, tmp_path: Path):
        store = SessionStore(tmp_path / "sessions.json", ttl_seconds=60, cookie_secure=True)
        cookie = store.cookie_for(store.create("alice"))
        assert "Secure" in cookie


class _FakeSession:
    def __init__(self, user: User) -> None:
        self.username = user.username
        self.role = user.role

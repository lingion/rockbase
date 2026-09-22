"""Authentication, sessions, and CSRF for the Rockbase console.

Stdlib-only. Persists sessions as JSON under restrictive permissions; lookup is
constant-time; passwords are stored as PBKDF2-HMAC digests and never logged.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]



_ALLOWED_ROLES = ("viewer", "operator")


def _coerce_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _coerce_hex(name: str, value: object) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a hex string")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be valid hex") from exc
    if not decoded:
        raise ValueError(f"{name} must be non-empty")
    return decoded


@dataclass(frozen=True)
class User:
    username: str
    role: Literal["viewer", "operator"]
    salt_hex: str
    password_hash_hex: str
    iterations: int


@dataclass
class Session:
    session_id: str
    csrf_token: str
    username: str
    role: str
    created_at: float
    expires_at: float
    session_id_hash: str = field(default="")
    csrf_token_hash: str = field(default="")


def hash_password(password: str, *, iterations: int = 200_000) -> tuple[str, str, int]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return salt.hex(), digest.hex(), iterations


def _pbkdf2(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)


def verify_password(user: User, password: str) -> bool:
    salt = bytes.fromhex(user.salt_hex)
    expected = bytes.fromhex(user.password_hash_hex)
    actual = _pbkdf2(password, salt, user.iterations)
    return hmac.compare_digest(actual, expected)


def load_users(path: Path) -> dict[str, User]:
    if not path.exists():
        return {}
    raw = path.read_bytes()
    parsed = tomllib.loads(raw.decode("utf-8"))
    users: dict[str, User] = {}
    for entry in parsed.get("users", []):
        username = entry.get("username")
        if not isinstance(username, str) or not username:
            raise ValueError("user.username must be a non-empty string")
        role = entry.get("role")
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"user.role must be one of {_ALLOWED_ROLES}")
        salt = _coerce_hex("user.salt_hex", entry.get("salt_hex"))
        digest = _coerce_hex("user.password_hash_hex", entry.get("password_hash_hex"))
        iterations = _coerce_positive_int("user.iterations", entry.get("iterations"))
        users[username] = User(
            username=username,
            role=role,
            salt_hex=salt.hex(),
            password_hash_hex=digest.hex(),
            iterations=iterations,
        )
    return users


def require_role(session: Session, role: Literal["viewer", "operator"]) -> bool:
    order = {"viewer": 1, "operator": 2}
    return order.get(getattr(session, "role", ""), 0) >= order[role]


class SessionStore:
    """JSON-backed session store. Persists *hashed* session IDs only."""

    SESSION_TTL_DEFAULT = 8 * 3600

    def __init__(
        self,
        path: Path,
        *,
        ttl_seconds: int = SESSION_TTL_DEFAULT,
        cookie_secure: bool = False,
    ) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.cookie_secure = cookie_secure
        self._entries: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._entries = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._entries = {}

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        try:
            with open(fd, "w", encoding="utf-8") as handle:
                json.dump(self._entries, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
            try:
                import os
                os.chmod(temporary, 0o600)
            except OSError:  # pragma: no cover - non-POSIX
                pass
            import os
            os.replace(temporary, self.path)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, username: str, *, role: str = "operator") -> Session:
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + self.ttl_seconds
        self._entries[self._hash(session_id)] = {
            "csrf_hash": self._hash(csrf_token),
            "username": username,
            "role": role,
            "created_at": now,
            "expires_at": expires_at,
        }
        self._flush()
        return Session(
            session_id=session_id,
            csrf_token=csrf_token,
            username=username,
            role=role,
            created_at=now,
            expires_at=expires_at,
            session_id_hash=self._hash(session_id),
            csrf_token_hash=self._hash(csrf_token),
        )

    def get(self, session_id: str) -> Session | None:
        entry = self._entries.get(self._hash(session_id))
        if entry is None:
            return None
        if entry.get("expires_at", 0) < time.time():
            return None
        # Re-derive csrf_token is impossible; return Session without it but
        # preserve the hash so the caller can compare against supplied tokens.
        return Session(
            session_id=session_id,
            csrf_token="",
            username=entry["username"],
            role=entry["role"],
            created_at=entry["created_at"],
            expires_at=entry["expires_at"],
            session_id_hash=self._hash(session_id),
            csrf_token_hash=entry["csrf_hash"],
        )

    def csrf_valid(self, session: Session, supplied: str) -> bool:
        if not supplied:
            return False
        return hmac.compare_digest(session.csrf_token_hash, self._hash(supplied))

    def revoke(self, session_id: str) -> None:
        self._entries.pop(self._hash(session_id), None)
        self._flush()

    def cookie_for(self, session: Session) -> str:
        flags = ["HttpOnly", "SameSite=Strict", "Path=/"]
        if self.cookie_secure:
            flags.append("Secure")
        return f"rockbase_console_sid={session.session_id}; {'; '.join(flags)}"
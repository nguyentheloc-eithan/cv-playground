"""Passwords, sessions, device keys, login throttling."""
import hashlib
import hmac
import secrets
import threading
import time

from . import settings


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got.hex(), h)
    except Exception:
        return False


def check_password_rules(pw: str):
    rules = settings.get().security.password
    if len(pw) < rules.min_length:
        return f"password must be at least {rules.min_length} characters"
    if not any(ch.isalpha() for ch in pw) or not any(ch.isdigit() for ch in pw):
        return "password must contain at least one letter and one number"
    return None


def _digest(token: str) -> str:
    """Tokens and device keys are stored as keyed hashes, so a database leak does not leak working credentials."""
    key = settings.get().security.secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


hash_token = _digest
hash_key = _digest


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_device_key() -> str:
    return "sk_" + secrets.token_urlsafe(settings.get().security.device.key_bytes)


def claim_code() -> str:
    a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    pre = settings.get().tenancy.claim_code_prefix
    return f"{pre}-" + "".join(secrets.choice(a) for _ in range(4)) + "-" + "".join(secrets.choice(a) for _ in range(4))


def temp_password() -> str:
    a = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(a) for _ in range(10)) + "7"


class LoginGuard:
    """Counts failed logins per (email, ip). In memory: fine for one worker; use a shared store (Redis) for many."""

    def __init__(self):
        self.fails = {}
        self.lock = threading.Lock()

    def blocked(self, key):
        cfg = settings.get().security.login_protection
        with self.lock:
            n, until = self.fails.get(key, (0, 0))
            return until > time.time() and n >= cfg.max_failures

    def fail(self, key):
        cfg = settings.get().security.login_protection
        with self.lock:
            n, _ = self.fails.get(key, (0, 0))
            self.fails[key] = (n + 1, time.time() + cfg.lock_minutes * 60)

    def ok(self, key):
        with self.lock:
            self.fails.pop(key, None)


guard = LoginGuard()


def sign(msg: str) -> str:
    return _digest("sign:" + msg)[:32]


def verify_sig(msg: str, sig: str) -> bool:
    return hmac.compare_digest(sign(msg), sig)

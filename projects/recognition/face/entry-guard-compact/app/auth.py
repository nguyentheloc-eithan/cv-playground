"""Login helpers: password hashing and signed session tokens. Python standard library only.

Password: stored as  scrypt$<salt>$<hash>  (slow on purpose, so guessing is expensive).
Session : a token "user_id.expiry.signature" kept in an HttpOnly cookie. The signature is an
          HMAC with a secret key stored in data/secret.key, so nobody can forge a token.
"""
import base64
import hashlib
import hmac
import os
import secrets
import time


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password, stored):
    try:
        _, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                n=2**14, r=8, p=1)
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)  # constant-time compare


def load_secret(path):
    """Read the signing key, creating it on first start."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secrets.token_bytes(32))
        os.chmod(path, 0o600)
    return path.read_bytes()


def _sign(secret, text):
    return hmac.new(secret, text.encode(), hashlib.sha256).hexdigest()


def make_token(secret, user_id, hours, epoch=0):
    """`epoch` is the user's session counter. Changing a password (or disabling the user) raises the
    counter on the server, which makes every older token stop working."""
    body = f"{user_id}.{epoch}.{int(time.time() + hours * 3600)}"
    return f"{body}.{_sign(secret, body)}"


def read_token(secret, token):
    """Return (user_id, epoch) if the token is genuine and not expired, else None."""
    try:
        user_id, epoch, expiry, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(secret, f"{user_id}.{epoch}.{expiry}")):
            return None
        if int(expiry) < time.time():
            return None
        return int(user_id), int(epoch)
    except (ValueError, AttributeError):
        return None


def password_problem(password, username, minimum=12):
    """Why this password is not acceptable, or None when it is fine."""
    if len(password) < minimum:
        return f"Password must be at least {minimum} characters"
    if len(set(password)) < 5:
        return "Password is too repetitive"
    if username and username.lower() in password.lower():
        return "Password must not contain the user name"
    return None

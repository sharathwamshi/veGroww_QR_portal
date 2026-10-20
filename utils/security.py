"""
Small, dependency-free security helpers:

  * CSRF tokens for every POST form
  * sign-in throttling (per IP + account) to slow down password guessing
  * safe redirect targets for ?next=
  * safe href values for user-supplied links on public pages
  * basic email / password validation
"""

import hmac
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from flask import request, session
from markupsafe import Markup, escape

# ---------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------
CSRF_SESSION_KEY = "_csrf_token"
CSRF_FIELD = "_csrf_token"


def csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_field() -> Markup:
    return Markup(f'<input type="hidden" name="{CSRF_FIELD}" value="{escape(csrf_token())}">')


def csrf_valid() -> bool:
    expected = session.get(CSRF_SESSION_KEY)
    sent = request.form.get(CSRF_FIELD) or request.headers.get("X-CSRF-Token")
    return bool(expected and sent and hmac.compare_digest(str(expected), str(sent)))


# ---------------------------------------------------------------------
# Sign-in throttling
# In-process memory: fine for a single server process. Behind several
# gunicorn workers each worker counts separately, which still slows an
# attacker down considerably.
# ---------------------------------------------------------------------
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
LOCK_SECONDS = 15 * 60

_lock = threading.Lock()
_failures = {}      # key -> [timestamps]
_locked_until = {}  # key -> unix time


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _keys(identifier: str):
    ident = (identifier or "").strip().lower()
    return (f"acct:{_client_ip()}:{ident}", f"ip:{_client_ip()}")


def login_locked(identifier: str) -> int:
    """Seconds until the caller may try again, or 0 if not locked."""
    now = time.time()
    with _lock:
        waits = [int(_locked_until.get(k, 0) - now) for k in _keys(identifier)]
    wait = max(waits)
    return wait if wait > 0 else 0


def register_failure(identifier: str):
    now = time.time()
    acct_key, ip_key = _keys(identifier)
    with _lock:
        for key, limit in ((acct_key, MAX_FAILURES), (ip_key, MAX_FAILURES * 4)):
            recent = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
            recent.append(now)
            _failures[key] = recent
            if len(recent) >= limit:
                _locked_until[key] = now + LOCK_SECONDS
                _failures[key] = []


def clear_failures(identifier: str):
    acct_key, _ip_key = _keys(identifier)
    with _lock:
        _failures.pop(acct_key, None)
        _locked_until.pop(acct_key, None)


# ---------------------------------------------------------------------
# Redirect targets
# ---------------------------------------------------------------------
def safe_next(target: str):
    """Only allow same-site relative paths, e.g. '/vcard/'. Anything else -> None."""
    if not target:
        return None
    target = target.strip()
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


# ---------------------------------------------------------------------
# User-supplied links shown on public pages
# ---------------------------------------------------------------------
_ALLOWED_SCHEMES = ("http://", "https://", "mailto:", "tel:")
_HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


def normalise_link(value: str) -> str:
    """
    Turn what someone typed into a link that is safe to put in href.

    'instagram.com/me' -> 'https://instagram.com/me'. Anything with a
    scheme other than http(s)/mailto/tel (javascript:, data:, ...) is
    rejected and returns ''.
    """
    value = (value or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    if lowered.startswith(_ALLOWED_SCHEMES):
        return value
    if _HAS_SCHEME.match(value) and not re.match(r"^[^:/]+:\d", value):
        return ""
    return "https://" + value.lstrip("/")


def safe_href(value: str) -> str:
    """Template filter: never emit an unsafe href, even for old data."""
    return normalise_link(value) or "#"


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,185}\.[A-Za-z]{2,}$")
MIN_PASSWORD = 8


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match((value or "").strip()))


def password_problem(password: str, confirm: str = None):
    """Return a human message describing what's wrong, or None."""
    if not password or len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters for the password."
    if password.strip() != password:
        return "The password can't start or end with a space."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Include at least one letter and one number in the password."
    if confirm is not None and password != confirm:
        return "The two passwords don't match."
    return None

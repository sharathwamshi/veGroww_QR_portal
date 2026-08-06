"""
Configuration for the Vegroww QR & ID Card Portal.

Every value is driven by environment variables, which are loaded from a
`.env` file sitting next to this module (see `.env.example`). Real
environment variables always win over `.env`, so the same codebase moves
from a laptop to a production server with no code changes.
"""

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load qr_id_portal/.env BEFORE the Config class body is evaluated.
# override=False -> anything already exported in the real environment wins.
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)


def _env_str(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    return default if value is None or value.strip() == "" else value.strip()


def _env_raw(key: str, default: str = "") -> str:
    """
    Like _env_str but honours an explicitly blank value.

    `DB_PASSWORD=` in .env means "this account has no password" - it must
    NOT silently fall back to the default. Also skips stripping, since
    leading/trailing spaces can be part of a real password.
    """
    value = os.environ.get(key)
    return default if value is None else value


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env_str(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    return _env_str(key, "1" if default else "0").lower() in ("1", "true", "yes", "on")


def _env_set(key: str, default: str) -> set:
    return {item.strip().lower() for item in _env_str(key, default).split(",") if item.strip()}


class Config:
    # ---------------------------------------------------------------
    # Core Flask
    # ---------------------------------------------------------------
    SECRET_KEY = _env_str("SECRET_KEY", "vegroww-qr-portal-change-this-secret-key")

    # Dev server only (wsgi.py / gunicorn ignore these)
    FLASK_DEBUG = _env_bool("FLASK_DEBUG", True)
    FLASK_HOST = _env_str("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = _env_int("FLASK_PORT", 5000)

    # ---------------------------------------------------------------
    # Database (MySQL) - local storage only, no external services
    # ---------------------------------------------------------------
    DB_USER = _env_str("DB_USER", "root")
    # Blank is a valid value here (passwordless local MySQL) - see _env_raw.
    DB_PASSWORD = _env_raw("DB_PASSWORD", "password")
    DB_HOST = _env_str("DB_HOST", "localhost")
    DB_PORT = _env_str("DB_PORT", "3306")
    DB_NAME = _env_str("DB_NAME", "vegroww_qr_portal")

    # Passwords with @ / # / : etc. must be percent-encoded inside a DSN.
    SQLALCHEMY_DATABASE_URI = _env_str(
        "DATABASE_URL",
        "mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}?charset=utf8mb4".format(
            user=quote_plus(DB_USER),
            pwd=quote_plus(DB_PASSWORD),
            host=DB_HOST,
            port=DB_PORT,
            name=DB_NAME,
        ),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": _env_int("DB_POOL_RECYCLE", 280),
    }

    # If your DB is provisioned from schema.sql, set this to 0 so the app
    # does not try to run db.create_all() on every boot.
    AUTO_CREATE_TABLES = _env_bool("AUTO_CREATE_TABLES", True)

    # ---------------------------------------------------------------
    # Static login (single admin account, no user table / signup flow)
    # ---------------------------------------------------------------
    ADMIN_USERNAME = _env_str("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = _env_raw("ADMIN_PASSWORD", "Vegroww@123")

    # ---------------------------------------------------------------
    # Local file storage (no cloud storage - everything on disk)
    # ---------------------------------------------------------------
    UPLOAD_ROOT = os.path.abspath(
        _env_str("UPLOAD_ROOT", os.path.join(BASE_DIR, "static", "uploads"))
    )
    PHOTO_DIR = os.path.join(UPLOAD_ROOT, "photos")
    LOGO_DIR = os.path.join(UPLOAD_ROOT, "logos")
    SIGNATURE_DIR = os.path.join(UPLOAD_ROOT, "signatures")
    ID_CARD_DIR = os.path.join(UPLOAD_ROOT, "id_cards")
    QR_DIR = os.path.join(UPLOAD_ROOT, "qr_codes")
    IMAGE_QR_SOURCE_DIR = os.path.join(UPLOAD_ROOT, "images")
    VCARD_IMAGE_DIR = os.path.join(UPLOAD_ROOT, "vcards")
    INVITE_IMAGE_DIR = os.path.join(UPLOAD_ROOT, "invitations")

    # Upload cap (covers bulk zip of photos)
    MAX_CONTENT_LENGTH = _env_int("MAX_UPLOAD_MB", 30) * 1024 * 1024

    ALLOWED_IMAGE_EXTENSIONS = _env_set("ALLOWED_IMAGE_EXTENSIONS", "png,jpg,jpeg,webp")
    ALLOWED_DATA_EXTENSIONS = _env_set("ALLOWED_DATA_EXTENSIONS", "csv,xlsx,xls")
    ALLOWED_ARCHIVE_EXTENSIONS = _env_set("ALLOWED_ARCHIVE_EXTENSIONS", "zip")

    # ---------------------------------------------------------------
    # Public base URL - used to build the link that gets embedded in
    # QR codes before shortening. Point this at wherever the app is
    # actually reachable (e.g. https://id.yourcompany.com) in production.
    # ---------------------------------------------------------------
    PUBLIC_BASE_URL = _env_str("PUBLIC_BASE_URL", "http://127.0.0.1:5000")

    # TinyURL free endpoint - no API key required for basic shortening
    TINYURL_API = _env_str("TINYURL_API", "https://tinyurl.com/api-create.php")
    TINYURL_TIMEOUT = _env_int("TINYURL_TIMEOUT", 5)  # fail soft to full URL if unreachable

    # ---------------------------------------------------------------
    # Branding
    # ---------------------------------------------------------------
    APP_NAME = _env_str("APP_NAME", "Vegroww QR Portal")
    APP_TAGLINE = _env_str("APP_TAGLINE", "QR Code Generator powered by Vegroww")
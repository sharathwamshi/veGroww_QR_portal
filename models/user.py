"""
Accounts, per-user feature access, signup defaults and usage history.

Table definitions mirror migrations/001_multi_user_accounts.sql exactly,
so the app runs against a database migrated with that file and
AUTO_CREATE_TABLES=0.
"""

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

ROLE_ADMIN = "admin"
ROLE_USER = "user"

STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_DISABLED = "disabled"

PERIOD_LIFETIME = "lifetime"
PERIOD_MONTHLY = "monthly"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    # Admin signs in with a username (from .env); everyone else uses
    # their email, which is also stored here so lookups are uniform.
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(190), nullable=True, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default=ROLE_USER, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE, index=True)

    limit_period = db.Column(db.String(20), nullable=False, default=PERIOD_LIFETIME)
    total_limit = db.Column(db.Integer, nullable=True)   # None = no overall cap

    # Bumped whenever the password changes or the account is disabled, so
    # any session issued before that moment stops working.
    session_version = db.Column(db.Integer, nullable=False, default=1)

    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = db.relationship(
        "UserPermission", backref="user", cascade="all, delete-orphan", lazy="selectin"
    )

    # ---- password ----
    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)
        self.session_version = (self.session_version or 0) + 1

    def check_password(self, raw: str) -> bool:
        try:
            return check_password_hash(self.password_hash, raw or "")
        except (ValueError, TypeError):
            return False

    # ---- role / status helpers ----
    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def initials(self) -> str:
        parts = [p for p in (self.name or "").split() if p]
        if not parts:
            return "?"
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

    def permission_for(self, module: str):
        for perm in self.permissions:
            if perm.module == module:
                return perm
        return None

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class UserPermission(db.Model):
    """One row per (user, module): is it switched on, and how many allowed."""

    __tablename__ = "user_permissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module = db.Column(db.String(40), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    quota = db.Column(db.Integer, nullable=True)   # None = unlimited

    __table_args__ = (db.UniqueConstraint("user_id", "module", name="uq_user_module"),)


class DefaultPermission(db.Model):
    """What a brand-new account receives, per module."""

    __tablename__ = "default_permissions"

    module = db.Column(db.String(40), primary_key=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    quota = db.Column(db.Integer, nullable=True)


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    setting_key = db.Column(db.String(80), primary_key=True)
    setting_value = db.Column(db.String(255), nullable=True)

    @classmethod
    def get(cls, key: str, default=None):
        row = db.session.get(cls, key)
        if row is None or row.setting_value is None:
            return default
        return row.setting_value

    @classmethod
    def put(cls, key: str, value):
        row = db.session.get(cls, key)
        if row is None:
            row = cls(setting_key=key)
            db.session.add(row)
        row.setting_value = None if value is None else str(value)


class UsageLog(db.Model):
    """One row per creation — drives monthly limits and usage history."""

    __tablename__ = "usage_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module = db.Column(db.String(40), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index("ix_usage_user_module_time", "user_id", "module", "created_at"),
    )

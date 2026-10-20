"""
Runs once at startup, inside the app context. Every step is idempotent.

1. Schema check — confirms the multi-user migration has been applied, and
   stops with a clear instruction if it hasn't, rather than failing later
   on the first query.
2. Admin seed — if there is no admin account yet, creates one from
   ADMIN_USERNAME / ADMIN_PASSWORD in .env. After that the database is the
   source of truth; .env is not read for the password again.
3. Ownership backfill — any record without an owner (everything that
   existed before the migration) is assigned to the admin.
4. Defaults — makes sure every module has a "new user default" row and
   the signup setting exists.
"""

import logging

from sqlalchemy import inspect

from extensions import db
from models import (AppSetting, Batch, DefaultPermission, ImageQR, Invitation,
                    UpiQR, UrlQR, User, VCard)
from models.user import ROLE_ADMIN, STATUS_ACTIVE
from utils.modules import FALLBACK_DEFAULT_QUOTA, MODULE_KEYS

log = logging.getLogger(__name__)

OWNED_MODELS = (Batch, VCard, Invitation, UrlQR, ImageQR, UpiQR)
NEW_TABLES = ("users", "user_permissions", "default_permissions", "app_settings", "usage_log")

MIGRATION_HINT = (
    "The database hasn't been upgraded for user accounts yet. Back up the "
    "database, then import migrations/001_multi_user_accounts.sql into it "
    "(phpMyAdmin -> select the database -> Import), and start the app again. "
    "The migration only adds tables and one column; it doesn't change or "
    "remove existing data."
)


class SchemaNotReady(RuntimeError):
    pass


def check_schema():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    missing = [t for t in NEW_TABLES if t not in tables]
    for model in OWNED_MODELS:
        table = model.__tablename__
        if table not in tables:
            missing.append(table)
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "owner_id" not in cols:
            missing.append(f"{table}.owner_id")

    if missing:
        raise SchemaNotReady(f"{MIGRATION_HINT}\nMissing: {', '.join(missing)}")


def ensure_admin(config) -> User:
    admin = User.query.filter_by(role=ROLE_ADMIN).order_by(User.id.asc()).first()
    if admin:
        return admin

    username = (config.get("ADMIN_USERNAME") or "admin").strip()
    password = config.get("ADMIN_PASSWORD") or ""
    if not password:
        raise RuntimeError("ADMIN_PASSWORD is empty in .env — set it so the admin account can be created.")

    clash = User.query.filter_by(username=username).first()
    if clash:
        raise RuntimeError(
            f"Cannot create the admin account: the username '{username}' is already "
            "used by a regular account. Change ADMIN_USERNAME in .env."
        )

    admin = User(
        name="Administrator",
        username=username,
        email=None,
        role=ROLE_ADMIN,
        status=STATUS_ACTIVE,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    log.info("Created admin account '%s' from .env", username)
    return admin


def backfill_ownership(admin: User) -> int:
    """
    Give un-owned rows to the admin, changing ONLY owner_id.

    A plain ORM/Core UPDATE would also fire the `onupdate` hook on
    updated_at and silently rewrite every legacy row's timestamp, so
    updated_at is explicitly set to its own current value.
    """
    assigned = 0
    for model in OWNED_MODELS:
        table = model.__table__
        values = {table.c.owner_id: admin.id}
        if "updated_at" in table.c:
            values[table.c.updated_at] = table.c.updated_at
        result = db.session.execute(
            table.update().where(table.c.owner_id.is_(None)).values(values)
        )
        assigned += result.rowcount or 0
    if assigned:
        db.session.commit()
        log.info("Assigned %s existing record(s) to the admin account", assigned)
    return assigned


def ensure_defaults():
    changed = False
    present = {row.module for row in DefaultPermission.query.all()}
    for key in MODULE_KEYS:
        if key not in present:
            db.session.add(DefaultPermission(
                module=key, enabled=True, quota=FALLBACK_DEFAULT_QUOTA.get(key)
            ))
            changed = True
    if db.session.get(AppSetting, "signup_mode") is None:
        db.session.add(AppSetting(setting_key="signup_mode", setting_value="approval"))
        changed = True
    if db.session.get(AppSetting, "default_limit_period") is None:
        db.session.add(AppSetting(setting_key="default_limit_period", setting_value="lifetime"))
        changed = True
    if changed:
        db.session.commit()


def run(app):
    with app.app_context():
        if app.config.get("AUTO_CREATE_TABLES", True):
            # Creates any MISSING tables only. It never alters or drops an
            # existing table — that's what the migration file is for.
            db.create_all()
        check_schema()
        admin = ensure_admin(app.config)
        backfill_ownership(admin)
        ensure_defaults()

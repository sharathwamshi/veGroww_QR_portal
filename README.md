# QR Saathi

*Powered by Akruthi India*

A self-hosted Flask portal where people sign up, sign in and create QR-based
content inside their **own private account**. An administrator approves
accounts, decides which features each person can use, and sets how many
items they can create.

## Features

| Module | What it makes | Public page (what the QR opens) |
|---|---|---|
| **ID Card Generator** | Employee ID cards in batches (CSV/Excel import or manual entry) with a verification QR | `/id-cards/verify/<id>` |
| **Digital vCards** | Shareable contact pages with an *Add contact* (.vcf) button | `/vcard/v/<slug>` |
| **Invitations** | Event cards (24 occasion types) with calendar (.ics) and Maps buttons | `/invitation/i/<slug>` |
| **URL QR** | A QR for any web address, shortened via TinyURL | — |
| **Image QR** | Upload an image, get a QR that opens it | `/image-qr/file/<name>` |
| **UPI Payment QR** | `upi://pay` codes for any UPI app | — |

### Accounts and access

- **Sign up / sign in.** People sign up with their name, email and password, and sign in with that email. Sign-up can be *approval required* (the default), *open*, or *closed*.
- **Privacy.** Everything a user creates belongs to them. Lists only show their own items, and opening someone else's item by changing the URL returns "not found". Public pages stay public by design.
- **Administrator.**
  - Approves, disables or deletes accounts, and resets passwords.
  - Turns each feature on or off per user, and sets per-feature limits plus an optional overall limit.
  - Limits are counted either as a total at any time (deleting frees a slot) or per calendar month.
  - **Access settings** holds the *new user defaults* copied onto every new account.
- **Feature switched off.** Everything the user already made stays online and viewable/downloadable ("view only"); they can't create or change anything in that feature.
- **The admin sees counts and usage, not other users' content.**

## Requirements

- Python 3.10+
- MySQL 5.7/8.x or MariaDB 10.3+ (XAMPP works)

```bash
pip install -r requirements.txt
cp env.example .env      # then edit .env
```

## Database

### Upgrading an existing installation (keeps all data)

1. **Back up**: phpMyAdmin → your database → *Export* → *Go*.
2. Select your portal database (the `DB_NAME` in `.env`) → *Import* →
   `migrations/001_multi_user_accounts.sql` → *Go*.
3. Start the app.

The migration **only adds**: five new tables, and one nullable `owner_id`
column (with an index and a foreign key) on `batches`, `vcards`,
`invitations`, `url_qrs`, `image_qrs` and `upi_qrs`.
- It never drops, renames or rewrites anything.
- It is safe to run twice.
- The previous version of the code still runs against the migrated database, so rolling back is just putting the old code back.

On first start the app:
- creates the **admin account from `ADMIN_USERNAME` / `ADMIN_PASSWORD`**, so you sign in exactly as before;
- assigns **every existing record to the admin**.

Existing slugs, files and short links are untouched, so every QR code already printed keeps working.

If the code is started before the migration is imported, it stops with a
message explaining what to import. It does not half-start.

### Fresh installation

Import `schema.sql`, then `migrations/001_multi_user_accounts.sql`, and set
`AUTO_CREATE_TABLES=0`. Alternatively, leave `AUTO_CREATE_TABLES=1` on an
empty database and the app creates everything itself.

> `vegroww_portal_db.sql` and `vegroww_qr_portal_full.sql` start with
> `DROP DATABASE`. **Never import them into a database that holds real data.**

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Signs sign-in sessions. Use a long random value. |
| `SESSION_COOKIE_SECURE` | `1` once the portal is served only over https |
| `REMEMBER_ME_DAYS` | How long "Keep me signed in" lasts (default 30) |
| `DB_*` / `DATABASE_URL` | MySQL connection |
| `AUTO_CREATE_TABLES` | `0` when the schema is managed with the SQL files |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Used **once**, to create the admin on first start. Afterwards change the password in *My account*. |
| `UPLOAD_ROOT`, `MAX_UPLOAD_MB`, `ALLOWED_*_EXTENSIONS` | Local file storage |
| `PUBLIC_BASE_URL` | The address phones use to reach the portal (built into QR codes) |
| `TINYURL_API`, `TINYURL_TIMEOUT` | Link shortening (fails soft to the full link) |
| `APP_NAME`, `APP_TAGLINE` | Branding shown everywhere (default: *QR Saathi* / *Powered by Akruthi India*) |

**Forgotten admin password:** there is no email reset. Run this from the project folder:

```bash
python -c "from app import create_app; from extensions import db; from models import User; a=create_app(); c=a.app_context(); c.push(); u=User.query.filter_by(role='admin').first(); u.set_password('NewPassword123'); db.session.commit(); print('reset')"
```

## Run

```bash
python app.py                          # development
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app # production
```

## Security notes

- Passwords are hashed with Werkzeug (scrypt/pbkdf2).
- Changing or resetting a password, or disabling an account, signs that account out everywhere.
- Every form carries a CSRF token.
- Sign-in is throttled after repeated failures. The counter is held in memory, per process.
- `?next=` redirects only go to pages on this site.
- Website and social links on public vCards are restricted to http(s), so `javascript:` links are dropped.

## Project structure

```
app.py                  App factory: request hooks (user, CSRF, module access), template helpers
config.py               Environment-driven configuration
migrations/             Importable, additive SQL migrations
models/                 user.py (accounts, permissions, defaults, settings, usage) + one file per module
routes/                 auth, account, admin, dashboard + one blueprint per module
utils/
  modules.py            The six modules, described once (labels, icons, public endpoints)
  access.py             Ownership checks, feature access and limit maths
  bootstrap.py          Start-up: schema check, admin seed, ownership backfill
  security.py           CSRF, sign-in throttling, safe redirects/links, validation
  cleanup.py            Delete records together with their files
  ...                   QR, ID card rendering, bulk import, invitations, vCards
templates/              Jinja templates (admin/ for the admin area)
static/                 CSS and JS
```

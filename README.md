# Vegroww QR & ID Card Portal

A self-hosted Flask portal for:
1. **ID Card Generator** — bulk or manual employee data entry → photo upload → generated ID card with an embedded verification QR code.
2. **Image QR** — upload any image, get a QR code that opens it.
3. **UPI Payment QR** — generate a scannable UPI payment QR from a UPI ID and an optional fixed amount.

All storage (photos, logos, signatures, generated cards, QR codes) is local disk under `static/uploads/`. Data is stored in **MySQL**.

---

## 1. Requirements

- Python 3.10+
- MySQL Server 8.x (running locally or reachable over the network)
- `pip`

## 2. Setup

```bash
cd qr_id_portal
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Create the database

Import `schema.sql` straight into MySQL — it creates the database, all four
tables, indexes and foreign keys:

```bash
mysql -u root -p < schema.sql
```

Or import the same file through phpMyAdmin / MySQL Workbench / HeidiSQL.
If your hosting panel doesn't allow `CREATE DATABASE`, comment out the two
lines marked `[PANEL]` at the top of `schema.sql`, select your database
first, then import.

Alternatively skip this and let the app create the tables itself on first
run (`AUTO_CREATE_TABLES=1`, the default).

### Configure environment variables

All configuration lives in a `.env` file next to `config.py`. Copy the
template and edit it:

```bash
cp .env.example .env
```

Real environment variables (e.g. `export DB_PASSWORD=...`, systemd
`Environment=`, Docker `-e`) always override the `.env` file, so the same
build works locally and in production.

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret | change this in production |
| `FLASK_DEBUG`, `FLASK_HOST`, `FLASK_PORT` | Dev-server settings (ignored under gunicorn) | 1 / 0.0.0.0 / 5000 |
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` | MySQL connection | root / password / localhost / 3306 / vegroww_qr_portal |
| `DATABASE_URL` | Full DSN — overrides all `DB_*` values if set | built from `DB_*` |
| `AUTO_CREATE_TABLES` | Run `db.create_all()` on boot. Set to `0` after importing `schema.sql` | 1 |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Static login credentials | admin / Vegroww@123 |
| `UPLOAD_ROOT` | Where photos/logos/cards/QRs are stored. Blank = `static/uploads` | static/uploads |
| `MAX_UPLOAD_MB` | Upload size cap | 30 |
| `ALLOWED_IMAGE_EXTENSIONS`, `ALLOWED_DATA_EXTENSIONS`, `ALLOWED_ARCHIVE_EXTENSIONS` | Comma-separated allowlists | png,jpg,jpeg,webp / csv,xlsx,xls / zip |
| `PUBLIC_BASE_URL` | Base URL the app is reachable at | http://127.0.0.1:5000 |
| `TINYURL_API`, `TINYURL_TIMEOUT` | QR link shortening endpoint and timeout | tinyurl api-create / 5s |
| `APP_NAME`, `APP_TAGLINE` | Branding shown in the UI | Vegroww QR Portal |

**Important:** change `ADMIN_PASSWORD` and `SECRET_KEY` before using this
anywhere but your own machine, and keep `.env` out of git (`.gitignore`
already excludes it).

## 3. Run

```bash
python app.py
```

Visit `http://127.0.0.1:5000` and log in with the admin credentials above.

For production, use a WSGI server instead of the Flask dev server:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

---

## How the modules work

### ID Card Generator
1. **Create a Batch** — set the company name, address, logo and issuing-authority signature once. Every card in the batch reuses these.
2. **Add employees** — either:
   - **Bulk Upload**: a `.csv`/`.xlsx`/`.xls` file. Column headers are matched flexibly against: `Sr. No`, `Name`, `Employee Code`, `Blood Group`, `Unit Landline Number`, `Emergency Contact Number`, `Employee Contact Number`. Only `Name` and `Employee Code` are required — everything else is optional.
   - **Manual Entry**: a form, with an optional photo upload right away.
3. Employees without a photo show as **Needs Photo** — upload one inline from the list, or via Edit.
4. Click **Generate** (single) or **Generate All Ready Cards** (batch) to render the ID card image and its verification QR code.
5. **Edit** any employee, replace their photo, and **Regenerate** to refresh the card and QR.
6. Each card's QR encodes a link to a public **verification page** (`/id-cards/verify/<id>`, no login required) showing the employee's photo, name, code and company — the link is shortened via TinyURL before being encoded, falling back to the full URL automatically if TinyURL can't be reached.

### Image QR
Upload any image → it's saved locally and served at a stable local URL → that URL is shortened via TinyURL and encoded into a QR code. Manage (view/regenerate/delete) from the list page.

### UPI Payment QR
Enter a UPI ID (e.g. `name@bank`) and, optionally, a payee name / fixed amount / note. This builds a standard `upi://pay?...` deep link and encodes it directly — **not** shortened, since UPI apps require the raw `upi://` scheme to recognise it as a payment QR.

---

## Project structure

```
qr_id_portal/
├── app.py                  # App factory (create_app), dev server entrypoint
├── wsgi.py                 # Production WSGI entrypoint (gunicorn/uwsgi)
├── config.py                # All configuration (env-var driven)
├── extensions.py            # Shared SQLAlchemy instance
├── schema.sql                # Reference MySQL schema
├── requirements.txt
├── models/                  # Batch, IDCard, ImageQR, UpiQR
├── routes/                  # auth, dashboard, id_cards, image_qr, upi_qr blueprints
├── utils/
│   ├── qr_utils.py           # QR generation + TinyURL shortening
│   ├── id_card_render.py     # PIL-based ID card image renderer
│   ├── bulk_import.py         # CSV/Excel column-flexible reader
│   ├── file_helpers.py        # Upload/delete helpers
│   └── decorators.py          # @login_required
├── templates/                # Jinja templates (blue/white/navy theme)
└── static/
    ├── css/style.css
    └── uploads/               # Local storage: photos, logos, signatures, cards, qr_codes, images
```

## Notes & assumptions

- Login is a single static admin account (no signup flow, no per-user roles) — as requested.
- The reference employee sheet's "Issuing Authority Signature" is treated as a **batch-level** asset (one signature/stamp per company, applied to every card in that batch), since it repeats per unit rather than varying per employee.
- QR error correction is set to **High**, so codes stay scannable even with the small "SCAN TO VERIFY" caption baked in around it.
- Everything runs and stores data locally — no cloud storage, no external services besides the optional TinyURL shortening call (which fails soft if there's no internet access).

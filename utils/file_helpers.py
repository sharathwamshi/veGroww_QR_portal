import os
import re
import uuid

from werkzeug.utils import secure_filename


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_upload(file_storage, destination_dir: str, prefix: str = "") -> str:
    """Save a Werkzeug FileStorage to disk with a collision-safe unique filename."""
    os.makedirs(destination_dir, exist_ok=True)
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower() if "." in original else "bin"
    filename = f"{prefix}{uuid.uuid4().hex[:10]}.{ext}"
    file_storage.save(os.path.join(destination_dir, filename))
    return filename


def delete_if_exists(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def safe_download_name(label: str, fallback: str = "qr-code") -> str:
    """
    Turn a title / employee name into a tidy, filesystem-safe download slug.

    Used for the `download_name` on QR and ID card downloads so the browser
    saves e.g. "EMP-014-priya-nair-qr.png" rather than "qr_a91f3c2b.png".
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (label or "")).strip("-").lower()
    return (slug or fallback)[:60]
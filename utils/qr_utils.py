"""
QR code generation utilities.

Every QR code that opens a web page encodes the portal's own address
directly (built from PUBLIC_BASE_URL), e.g.
    https://qr.yourcompany.com/vcard/v/priya-nair
No third-party link shortener is involved, so codes never depend on an
outside service and always show your own site when scanned.

UPI payment QR codes encode the standard `upi://pay?...` deep link that
payment apps read directly, per the NPCI UPI QR spec.
"""

import os
import uuid

import qrcode
from PIL import Image


def generate_qr_image(data: str, box_size: int = 10, border: int = 3) -> Image.Image:
    """Build a QR code PIL image. Medium error correction keeps full-length URLs easy to scan."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="#0B2545", back_color="white").convert("RGB")


def save_qr_for_url(url: str, destination_dir: str, filename_prefix: str):
    """
    Generate a QR code that opens `url` (the full site address).

    Returns (qr_filename, target_url, None). The third value is kept for
    the existing short-link columns, which are no longer filled in.
    """
    return save_qr_for_raw_data(url, destination_dir, filename_prefix), url, None


def save_qr_for_raw_data(raw_data: str, destination_dir: str, filename_prefix: str) -> str:
    """Generate a QR code for any text: a site URL or a upi:// payment link."""
    img = generate_qr_image(raw_data)
    qr_filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.png"
    os.makedirs(destination_dir, exist_ok=True)
    img.save(os.path.join(destination_dir, qr_filename))
    return qr_filename


def build_upi_uri(upi_id: str, payee_name: str = "", amount=None, note: str = "") -> str:
    """Build a standard UPI deep-link URI (upi://pay?...) per the NPCI QR spec."""
    from urllib.parse import quote

    params = [f"pa={quote(upi_id)}"]
    if payee_name:
        params.append(f"pn={quote(payee_name)}")
    if amount not in (None, "", 0):
        params.append(f"am={quote(str(amount))}")
    params.append("cu=INR")
    if note:
        params.append(f"tn={quote(note)}")
    return "upi://pay?" + "&".join(params)

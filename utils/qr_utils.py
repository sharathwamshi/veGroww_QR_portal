"""
QR code generation utilities.

Design note on "TinyURL encoded" QR codes:
    A long URL (query strings, IDs, tokens) makes for a visually dense QR
    code that is slower and less reliable to scan. Wherever this portal
    embeds a real HTTP(S) link in a QR code - a link to an uploaded image,
    or a link to a card's public view page - it first asks TinyURL for a
    short alias and encodes THAT instead. If TinyURL can't be reached
    (e.g. no internet on this machine), we fail soft and encode the
    original full URL so QR generation never breaks.

    UPI payment QR codes are the one exception: those encode a `upi://`
    deep link that UPI apps parse directly. It is not an HTTP URL, so
    shortening it would break compatibility with payment apps - it is
    encoded as-is, per the NPCI UPI QR spec.
"""

import io
import os
import uuid

import qrcode
import requests
from PIL import Image

from config import Config


def shorten_url(long_url: str) -> str:
    """Return a TinyURL-shortened link, or the original URL if shortening fails."""
    try:
        response = requests.get(
            Config.TINYURL_API,
            params={"url": long_url},
            timeout=Config.TINYURL_TIMEOUT,
        )
        if response.status_code == 200 and response.text.startswith("http"):
            return response.text.strip()
    except requests.RequestException:
        pass
    return long_url


def generate_qr_image(data: str, box_size: int = 10, border: int = 3) -> Image.Image:
    """Build a QR code PIL image (high error correction, so logos/photos can safely overlap)."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="#0B2545", back_color="white").convert("RGB")


def save_qr_for_url(long_url: str, destination_dir: str, filename_prefix: str, shorten: bool = True):
    """
    Generate a QR code for a URL, optionally shortening it first via TinyURL.

    Returns (qr_filename, target_url, short_url_or_None)
    """
    short_url = shorten_url(long_url) if shorten else None
    encoded_value = short_url or long_url

    img = generate_qr_image(encoded_value)
    qr_filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.png"
    os.makedirs(destination_dir, exist_ok=True)
    img.save(os.path.join(destination_dir, qr_filename))

    return qr_filename, long_url, short_url


def save_qr_for_raw_data(raw_data: str, destination_dir: str, filename_prefix: str) -> str:
    """Generate a QR code for raw data (e.g. a upi:// URI) with no shortening applied."""
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

"""
Renders a single professional, blue-themed employee ID card as a PNG.

Pure PIL (no external image service, no internet dependency for the
render itself) so this works entirely with local storage as required.
"""

import os
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------
NAVY = (11, 37, 69)          # #0B2545 - header / primary text
BLUE = (30, 91, 168)         # #1E5BA8 - accent
LIGHT_BLUE = (223, 236, 250) # #DFECFA - footer band / soft fills
WHITE = (255, 255, 255)
SLATE = (90, 104, 122)       # secondary text
BORDER = (200, 214, 230)

CARD_W, CARD_H = 650, 1020
HEADER_H = 190
PHOTO_SIZE = 230
FOOTER_H = 210

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = [f for f in FONT_CANDIDATES if ("Bold" in f or "arialbd" in f)] if bold else \
            [f for f in FONT_CANDIDATES if not ("Bold" in f or "arialbd" in f)]
    for path in names + FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit_text(draw, text, font, max_width):
    """Shrink text with an ellipsis if it doesn't fit max_width at the given font."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "...", font=font) > max_width:
        text = text[:-1]
    return text + "..." if text else text


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)
    return mask


def _circle_crop(img: Image.Image, size: int) -> Image.Image:
    img = ImageOps.fit(img, (size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def render_id_card(
    *,
    company_name: str,
    company_address: str,
    logo_path: str | None,
    signature_path: str | None,
    signature_label: str,
    photo_path: str,
    name: str,
    employee_code: str,
    blood_group: str,
    employee_contact: str,
    emergency_contact: str,
    landline: str,
    destination_dir: str,
) -> str:
    """Render the card and save it as a PNG. Returns the saved filename."""

    card = Image.new("RGB", (CARD_W, CARD_H), WHITE)
    draw = ImageDraw.Draw(card)

    # ---------------- Header ----------------
    draw.rectangle([0, 0, CARD_W, HEADER_H], fill=NAVY)
    draw.rectangle([0, HEADER_H, CARD_W, HEADER_H + 6], fill=BLUE)  # accent underline

    text_x = 30
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo = ImageOps.contain(logo, (110, 110))
            card.paste(logo, (24, (HEADER_H - logo.height) // 2 - 3), logo)
            text_x = 150
        except Exception:
            text_x = 30

    name_font = _font(30, bold=True)
    tagline_font = _font(16)
    draw.text((text_x, 55), _fit_text(draw, company_name, name_font, CARD_W - text_x - 20),
              font=name_font, fill=WHITE)
    draw.text((text_x, 100), "EMPLOYEE IDENTIFICATION CARD", font=tagline_font, fill=LIGHT_BLUE)

    addr_font = _font(13)
    addr_text = _fit_text(draw, company_address, addr_font, CARD_W - text_x - 20)
    draw.text((text_x, 128), addr_text, font=addr_font, fill=(200, 214, 235))

    # ---------------- Photo ----------------
    photo_top = HEADER_H + 30
    try:
        photo_img = Image.open(photo_path).convert("RGB")
    except Exception:
        photo_img = Image.new("RGB", (PHOTO_SIZE, PHOTO_SIZE), LIGHT_BLUE)
    photo_img = ImageOps.fit(photo_img, (PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)

    frame_pad = 6
    frame_box = [
        CARD_W // 2 - PHOTO_SIZE // 2 - frame_pad,
        photo_top - frame_pad,
        CARD_W // 2 + PHOTO_SIZE // 2 + frame_pad,
        photo_top + PHOTO_SIZE + frame_pad,
    ]
    draw.rounded_rectangle(frame_box, radius=14, fill=WHITE, outline=BLUE, width=4)
    card.paste(photo_img, (CARD_W // 2 - PHOTO_SIZE // 2, photo_top))

    # ---------------- Name & code ----------------
    y = photo_top + PHOTO_SIZE + 26
    big_name_font = _font(26, bold=True)
    name_disp = _fit_text(draw, name.upper(), big_name_font, CARD_W - 60)
    w = draw.textlength(name_disp, font=big_name_font)
    draw.text(((CARD_W - w) / 2, y), name_disp, font=big_name_font, fill=NAVY)

    y += 42
    code_font = _font(16, bold=True)
    code_text = f"EMP. CODE: {employee_code}"
    w = draw.textlength(code_text, font=code_font)
    pill_pad_x, pill_pad_y = 16, 8
    pill_box = [(CARD_W - w) / 2 - pill_pad_x, y - pill_pad_y,
                (CARD_W + w) / 2 + pill_pad_x, y + 20 + pill_pad_y]
    draw.rounded_rectangle(pill_box, radius=16, fill=BLUE)
    draw.text(((CARD_W - w) / 2, y), code_text, font=code_font, fill=WHITE)

    # ---------------- Details ----------------
    y += 60
    draw.line([(40, y), (CARD_W - 40, y)], fill=BORDER, width=2)
    y += 24

    label_font = _font(14, bold=True)
    value_font = _font(16)

    rows = [
        ("BLOOD GROUP", blood_group or "-"),
        ("EMPLOYEE CONTACT", employee_contact or "-"),
        ("EMERGENCY CONTACT", emergency_contact or "-"),
        ("UNIT LANDLINE", landline or "-"),
    ]
    for label, value in rows:
        draw.text((45, y), label, font=label_font, fill=SLATE)
        draw.text((CARD_W - 45 - draw.textlength(str(value), font=value_font), y - 3),
                   str(value), font=value_font, fill=NAVY)
        y += 34

    # ---------------- Footer (signature + QR placeholder note) ----------------
    footer_top = CARD_H - FOOTER_H
    draw.rectangle([0, footer_top, CARD_W, CARD_H], fill=LIGHT_BLUE)
    draw.rectangle([0, footer_top, CARD_W, footer_top + 4], fill=BLUE)

    # Signature (left)
    sig_font = _font(12)
    if signature_path and os.path.exists(signature_path):
        try:
            sig = Image.open(signature_path).convert("RGBA")
            sig = ImageOps.contain(sig, (140, 60))
            card.paste(sig, (40, footer_top + 20), sig)
        except Exception:
            pass
    draw.line([(40, footer_top + 90), (200, footer_top + 90)], fill=SLATE, width=1)
    draw.text((40, footer_top + 96), _fit_text(draw, signature_label, sig_font, 170),
              font=sig_font, fill=SLATE)

    # QR reserved area (bottom-right) - caller pastes the QR image after this
    # so it always sits inside [CARD_W-190, footer_top+15, CARD_W-30, footer_top+175]

    os.makedirs(destination_dir, exist_ok=True)
    filename = f"card_{employee_code}_{uuid.uuid4().hex[:6]}.png"
    card.save(os.path.join(destination_dir, filename))
    return filename, footer_top


def paste_qr_on_card(card_path: str, qr_path: str, footer_top: int):
    """Paste a generated QR code into the reserved footer slot of an already-rendered card."""
    card = Image.open(card_path).convert("RGB")
    qr = Image.open(qr_path).convert("RGB")
    qr = ImageOps.contain(qr, (150, 150))
    x = CARD_W - 40 - qr.width
    y = footer_top + (FOOTER_H - qr.height) // 2 + 2
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle([x - 8, y - 8, x + qr.width + 8, y + qr.height + 8],
                            radius=10, outline=BLUE, width=2, fill=WHITE)
    card.paste(qr, (x, y))
    small_font = _font(11)
    label = "SCAN TO VERIFY"
    w = draw.textlength(label, font=small_font)
    draw.text((x + (qr.width - w) / 2, y + qr.height + 10), label, font=small_font, fill=SLATE)
    card.save(card_path)

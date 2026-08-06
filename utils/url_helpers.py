"""
Public URL building.

`url_for(..., _external=True)` builds a URL from whatever host the request
arrived on. That means a QR generated while browsing 127.0.0.1 encodes
127.0.0.1 — useless on a phone. PUBLIC_BASE_URL in .env fixes the host so
generated links always point at wherever the app is really reachable.
"""

from urllib.parse import urlsplit, urlunsplit

from flask import current_app, url_for


def public_url_for(endpoint: str, **values) -> str:
    """
    Build an absolute URL, rewriting the host to PUBLIC_BASE_URL when set.

    Falls back to the request host if PUBLIC_BASE_URL is empty, so local
    development keeps working with no configuration.
    """
    url = url_for(endpoint, _external=True, **values)

    base = (current_app.config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return url

    base_parts = urlsplit(base)
    if not base_parts.netloc:
        return url

    url_parts = urlsplit(url)
    path = url_parts.path

    # Honour a sub-path in PUBLIC_BASE_URL, e.g. https://site.com/portal
    if base_parts.path and base_parts.path != "/":
        path = base_parts.path.rstrip("/") + path

    return urlunsplit((
        base_parts.scheme or url_parts.scheme,
        base_parts.netloc,
        path,
        url_parts.query,
        url_parts.fragment,
    ))

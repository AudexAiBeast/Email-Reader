from email.header import decode_header, make_header


def decode_hdr(value: str | None) -> str:
    """Decode a raw (possibly RFC 2047 encoded) header value into a plain string."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value

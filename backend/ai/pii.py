import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d .()-]{7,}\d)(?!\d)")


def mask_pii(text):
    """Replace emails, IPv4 addresses and phone-like numbers with placeholders. IP check runs
    before the phone check since a dotted IP would otherwise also match the digit-run pattern."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _IP_RE.sub("[IP]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    return text

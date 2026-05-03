from __future__ import annotations

import re

from pydantic import EmailStr, TypeAdapter


_email_adapter = TypeAdapter(EmailStr)


def normalize_phone_ru(raw: str) -> str | None:
    digits = re.sub(r"\D+", "", (raw or "").strip())
    if not digits:
        return None
    if len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 11 and digits[0] == "9":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return f"+{digits}"
    return None


def parse_login_contact(raw: str) -> tuple[str, str | None]:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty contact")
    if "@" in s:
        email = str(_email_adapter.validate_python(s))
        return email.lower(), None
    phone = normalize_phone_ru(s)
    if phone is None:
        raise ValueError("invalid phone")
    digits = re.sub(r"\D+", "", phone)
    synthetic = f"phone{digits}@reg.paw"
    return synthetic, phone


def parse_login_contact_lenient(raw: str) -> tuple[str, str | None]:
    try:
        return parse_login_contact(raw)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

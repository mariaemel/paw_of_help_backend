from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.help_request import HelpRequest
    from app.models.organization import Organization


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def stored_payment_bank_account(org: Organization, bank_account: str | None) -> str | None:
    p = _norm(bank_account)
    o = _norm(org.bank_account)
    return p if p is not None and p != o else None


def effective_payment_bank_account(req: HelpRequest) -> str | None:
    org = req.organization
    return _norm(req.payment_bank_account) or _norm(org.bank_account if org else None)


def uses_organization_payment_details(req: HelpRequest) -> bool:
    return _norm(req.payment_bank_account) is None

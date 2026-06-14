from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.animal import AnimalStatus
from app.modules.animals.age_format import format_age_months_ru
from app.modules.animals.tags import species_label_ru
from app.modules.help.bucket import help_bucket_for_orphan_request, help_bucket_for_request
from app.modules.help.repository import HelpRepository
from app.modules.help.schemas import HelpAnimalCard, HelpListResponse, HelpMonetaryBrief

TAB_ALL = "all"
TAB_ADOPT = "adopt"
TAB_FEED = "feed"
TAB_HEAL = "heal"
TAB_OTHER = "other"

_ALLOWED_TABS = frozenset({TAB_ALL, TAB_ADOPT, TAB_FEED, TAB_HEAL, TAB_OTHER})


def _age_tag_ru(months: int) -> str:
    return format_age_months_ru(months)


def _status_chip_ru(animal_status: str) -> str | None:
    if animal_status == AnimalStatus.LOOKING_FOR_HOME.value:
        return "Готова к пристрою"
    if animal_status == AnimalStatus.ON_TREATMENT.value:
        return "На лечении"
    if animal_status == AnimalStatus.IN_SHELTER.value:
        return "В приюте"
    if animal_status == AnimalStatus.LOOKING_FOR_FOSTER.value:
        return "Ищет передержку"
    return None


def _primary_photo(animal) -> str | None:
    photos = list(getattr(animal, "photos", ()) or ())
    prim = next((p for p in photos if getattr(p, "is_primary", False)), None)
    if not prim and photos:
        prim = photos[0]
    if prim is None:
        return None
    return f"{settings.media_url_prefix}/{prim.file_path}"


def _all_bucket_lines(animal) -> list[HelpMonetaryBrief]:
    rows: list[HelpMonetaryBrief] = []
    for hr in animal.help_requests or []:
        b = help_bucket_for_request(hr)
        if b is None:
            continue
        amt_raw = getattr(hr, "target_amount", None)
        amt: float | None = float(amt_raw) if amt_raw is not None and amt_raw > 0 else None
        rows.append(
            HelpMonetaryBrief(
                request_id=int(hr.id),
                help_bucket=b,
                line=str(hr.title).strip(),
                amount_rub=amt,
            )
        )
    rows.sort(key=lambda x: (x.amount_rub is None, -(x.amount_rub or 0.0)), reverse=False)
    return rows


def _buckets_present(adopt_ready: bool, monetaries: Iterable[HelpMonetaryBrief]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if adopt_ready:
        out.append("adopt")
        seen.add("adopt")
    for m in monetaries:
        if m.help_bucket not in seen:
            seen.add(m.help_bucket)
            out.append(m.help_bucket)
    return out


def _pick_preferred(monetary: list[HelpMonetaryBrief]) -> HelpMonetaryBrief | None:
    with_amount = [m for m in monetary if m.amount_rub is not None]
    if not with_amount:
        return None
    return max(with_amount, key=lambda m: float(m.amount_rub or 0.0))


def _animal_on_page(adopt_ready: bool, monetaries: list[HelpMonetaryBrief]) -> bool:
    if adopt_ready:
        return True
    return len(monetaries) > 0


def _scoped_monetary(all_mon: list[HelpMonetaryBrief], bucket: str | None) -> list[HelpMonetaryBrief]:
    if bucket is None:
        return list(all_mon)
    return [m for m in all_mon if m.help_bucket == bucket]


def _sort_tab_all(items: list[HelpAnimalCard]) -> None:
    def key(c: HelpAnimalCard) -> tuple[int, int, int]:
        has_pref = int(_pick_preferred(list(c.monetary)) is not None)
        urg = int(c.is_urgent)
        tie = int(c.animal_id or 0)
        if tie == 0 and c.monetary:
            tie = int(c.monetary[0].request_id)
        return (-has_pref, -urg, -tie)

    items.sort(key=key)


def _orphan_photo(hr) -> str | None:
    if hr.media_path:
        return f"{settings.media_url_prefix}/{hr.media_path}"
    org = getattr(hr, "organization", None)
    if org and getattr(org, "logo_path", None):
        return f"{settings.media_url_prefix}/{org.logo_path}"
    return None


def _monetary_brief(hr, bucket: str) -> HelpMonetaryBrief:
    amt_raw = getattr(hr, "target_amount", None)
    amt: float | None = float(amt_raw) if amt_raw is not None and amt_raw > 0 else None
    return HelpMonetaryBrief(
        request_id=int(hr.id),
        help_bucket=bucket,
        line=str(hr.title).strip(),
        amount_rub=amt,
    )


def _build_linked_fundraising_card(hr) -> HelpAnimalCard | None:
    animal = getattr(hr, "animal", None)
    if animal is None:
        return None
    bucket = help_bucket_for_request(hr)
    if bucket is None:
        return None
    return HelpAnimalCard(
        animal_id=int(animal.id),
        organization_id=int(hr.organization_id) if hr.organization_id is not None else None,
        name=animal.name,
        species_tag=species_label_ru(animal.species, animal.sex),
        age_tag=_age_tag_ru(int(animal.age_months or 0)),
        age_months=int(animal.age_months or 0),
        status_chip="Сбор средств",
        organization_name=(hr.organization.name if getattr(hr, "organization", None) else None),
        location_city=getattr(hr, "city", None) or getattr(animal, "location_city", None),
        is_urgent=bool(getattr(hr, "is_urgent", False)),
        monetary=[_monetary_brief(hr, bucket)],
        adopt_ready=False,
        primary_photo_url=_primary_photo(animal),
    )


def _build_help_orphan_card(hr) -> HelpAnimalCard | None:
    bucket = help_bucket_for_orphan_request(hr)
    if bucket is None:
        return None
    amt_raw = getattr(hr, "target_amount", None)
    amt: float | None = float(amt_raw) if amt_raw is not None and amt_raw > 0 else None
    monetaries = [
        HelpMonetaryBrief(
            request_id=int(hr.id),
            help_bucket=bucket,
            line=str(hr.title).strip(),
            amount_rub=amt,
        )
    ]
    org = getattr(hr, "organization", None)
    return HelpAnimalCard(
        animal_id=None,
        organization_id=int(hr.organization_id) if hr.organization_id is not None else None,
        name=str(hr.title).strip() or "Сбор средств",
        species_tag="сбор",
        age_tag="",
        age_months=0,
        status_chip="Сбор средств",
        organization_name=(org.name if org else None),
        location_city=getattr(hr, "city", None),
        is_urgent=bool(getattr(hr, "is_urgent", False)),
        monetary=monetaries,
        adopt_ready=False,
        primary_photo_url=_orphan_photo(hr),
    )


def _card_matches_tab(card: HelpAnimalCard, tl: str, bucket_filter: str | None) -> bool:
    adopt_ready = card.adopt_ready
    monetaries = list(card.monetary)
    buckets_all = _buckets_present(adopt_ready, monetaries)

    if tl == TAB_ADOPT:
        return adopt_ready
    if tl == TAB_ALL:
        return True
    if not bucket_filter or bucket_filter not in buckets_all:
        return False
    return bool(_scoped_monetary(monetaries, bucket_filter))


def _build_help_animal_card(animal) -> HelpAnimalCard | None:
    adopt_ready = animal.status == AnimalStatus.LOOKING_FOR_HOME.value
    monetaries = _all_bucket_lines(animal)
    if not _animal_on_page(adopt_ready, monetaries):
        return None
    return HelpAnimalCard(
        animal_id=int(animal.id),
        organization_id=int(animal.organization_id) if animal.organization_id is not None else None,
        name=animal.name,
        species_tag=species_label_ru(animal.species, animal.sex),
        age_tag=_age_tag_ru(int(animal.age_months or 0)),
        age_months=int(animal.age_months or 0),
        status_chip=_status_chip_ru(animal.status),
        organization_name=(animal.organization.name if animal.organization else None),
        location_city=getattr(animal, "location_city", None),
        is_urgent=bool(getattr(animal, "is_urgent", False)),
        monetary=list(monetaries),
        adopt_ready=adopt_ready,
        primary_photo_url=_primary_photo(animal),
    )


class HelpService:
    def __init__(self, repo: HelpRepository):
        self.repo = repo

    def list_cards(self, tab: str) -> HelpListResponse:
        tl = tab.strip().lower()
        if tl not in _ALLOWED_TABS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown tab")

        bucket_filter: str | None = None
        if tl == TAB_FEED:
            bucket_filter = "feed"
        elif tl == TAB_HEAL:
            bucket_filter = "heal"
        elif tl == TAB_OTHER:
            bucket_filter = "other"

        items_out: list[HelpAnimalCard] = []
        for animal in self.repo.list_candidate_animals():
            card = _build_help_animal_card(animal)
            if card is None or not _card_matches_tab(card, tl, bucket_filter):
                continue
            items_out.append(card)

        for hr in self.repo.list_orphan_fundraising_requests():
            card = _build_help_orphan_card(hr)
            if card is None or not _card_matches_tab(card, tl, bucket_filter):
                continue
            items_out.append(card)

        if tl == TAB_ALL:
            _sort_tab_all(items_out)
        else:
            items_out.sort(key=lambda c: (-int(c.is_urgent), -int(c.monetary[0].request_id if c.monetary else 0)))

        return HelpListResponse(tab=tl, total=len(items_out), items=items_out)

    def list_fundraising_cards(self) -> HelpListResponse:
        items_out: list[HelpAnimalCard] = []
        for hr in self.repo.list_public_fundraising_requests():
            if hr.animal_id is None:
                card = _build_help_orphan_card(hr)
            else:
                card = _build_linked_fundraising_card(hr)
            if card is not None:
                items_out.append(card)
        _sort_tab_all(items_out)
        return HelpListResponse(tab="fundraising", total=len(items_out), items=items_out)

    def list_cards_for_organization(self, organization_id: int) -> list[HelpAnimalCard]:
        items_out: list[HelpAnimalCard] = []
        for animal in self.repo.list_candidate_animals(organization_id=organization_id):
            card = _build_help_animal_card(animal)
            if card is not None:
                items_out.append(card)
        for hr in self.repo.list_orphan_fundraising_requests(organization_id=organization_id):
            card = _build_help_orphan_card(hr)
            if card is not None:
                items_out.append(card)
        _sort_tab_all(items_out)
        return items_out

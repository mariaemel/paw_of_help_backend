from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.animal import AnimalStatus
from app.modules.animals.tags import species_label_ru
from app.modules.help.bucket import help_bucket_for_request
from app.modules.help.repository import HelpRepository
from app.modules.help.schemas import HelpAnimalCard, HelpListResponse, HelpMonetaryBrief

TAB_ALL = "all"
TAB_ADOPT = "adopt"
TAB_FEED = "feed"
TAB_HEAL = "heal"
TAB_OTHER = "other"

_ALLOWED_TABS = frozenset({TAB_ALL, TAB_ADOPT, TAB_FEED, TAB_HEAL, TAB_OTHER})


def _age_tag_ru(months: int) -> str:
    if months < 12:
        m = months
        return f"{m} мес."
    y = months // 12
    md = months % 12
    if y == 1 and md <= 6:
        return "1 год"
    last = y % 10
    ll = y % 100
    noun = (
        "год"
        if last == 1 and ll != 11
        else ("года" if 2 <= last <= 4 and not (12 <= ll <= 14) else "лет")
    )
    return f"{y} {noun}"


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
        return (-has_pref, -urg, int(c.animal_id))

    items.sort(key=key)


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
            adopt_ready = animal.status == AnimalStatus.LOOKING_FOR_HOME.value
            monetaries = _all_bucket_lines(animal)
            buckets_all = _buckets_present(adopt_ready, monetaries)

            if not _animal_on_page(adopt_ready, monetaries):
                continue

            if tl == TAB_ADOPT:
                if not adopt_ready:
                    continue

            elif tl != TAB_ALL:
                if not bucket_filter or bucket_filter not in buckets_all:
                    continue
                if not _scoped_monetary(monetaries, bucket_filter):
                    continue

            card = HelpAnimalCard(
                animal_id=int(animal.id),
                name=animal.name,
                species_tag=species_label_ru(animal.species, animal.sex),
                age_tag=_age_tag_ru(int(animal.age_months or 0)),
                status_chip=_status_chip_ru(animal.status),
                organization_name=(animal.organization.name if animal.organization else None),
                location_city=getattr(animal, "location_city", None),
                is_urgent=bool(getattr(animal, "is_urgent", False)),
                monetary=list(monetaries),
                adopt_ready=adopt_ready,
                primary_photo_url=_primary_photo(animal),
            )
            items_out.append(card)

        if tl == TAB_ALL:
            _sort_tab_all(items_out)

        return HelpListResponse(tab=tl, total=len(items_out), items=items_out)

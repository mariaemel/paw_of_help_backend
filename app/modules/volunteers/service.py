import json

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.user import User, UserRole
from app.modules.animals.jsonutil import parse_json_list
from app.modules.volunteers.constants import (
    ANIMAL_TYPE_FILTER_OPTIONS,
    COMPETENCY_OPTIONS,
    COMPETENCY_PROFILE_TAG_BY_SLUG,
    COMPETENCY_SHORT_LABELS,
    EXPERIENCE_LEVEL_LABELS,
    EXPERIENCE_LEVEL_OPTIONS,
    HELP_FORMAT_LABELS,
    KNOWLEDGE_CATEGORY_LABELS,
    TRAVEL_AREA_MODE_LABELS,
    WEEKDAY_LABEL_RU,
    WEEKDAY_ORDER,
)
from app.modules.volunteers.repository import VolunteerRepository
from app.modules.volunteers.schemas import (
    CatalogOption,
    VolunteerCatalogsResponse,
    VolunteerDetail,
    VolunteerFilterParams,
    VolunteerListItem,
    VolunteerListResponse,
    VolunteerPublicArticleCard,
    VolunteerPublicLogistics,
    VolunteerTimeRange,
    VolunteerViewerActions,
    VolunteerWeekdayScheduleOut,
)

_ANIMAL_LABELS = {x["id"]: x["label"] for x in ANIMAL_TYPE_FILTER_OPTIONS if x["id"] != "all"}
_COMP_FULL = {x["id"]: x["label"] for x in COMPETENCY_OPTIONS}


def _parse_weekly_raw(raw: str | None) -> list[dict]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


class VolunteerService:
    def __init__(self, repo: VolunteerRepository):
        self.repo = repo

    def _media_url(self, path: str | None) -> str | None:
        if not path:
            return None
        return f"{settings.media_url_prefix}/{path}"

    @staticmethod
    def _competency_slugs_labels_from_profile(profile) -> tuple[list[str], list[str]]:
        assigns = list(profile.competency_assignments or [])
        pairs: list[tuple[int, str, str]] = []
        for a in assigns:
            it = a.competency_item
            if it is None:
                continue
            pairs.append((int(it.sort_order or 0), it.slug, it.label))
        pairs.sort(key=lambda x: (x[0], x[1]))
        return [p[1] for p in pairs], [p[2] for p in pairs]

    def _competency_tag_pills_from_profile(self, profile) -> list[str]:
        slugs, _ = self._competency_slugs_labels_from_profile(profile)
        out: list[str] = []
        for cid in slugs:
            label = COMPETENCY_SHORT_LABELS.get(cid) or _COMP_FULL.get(cid) or cid
            if label not in out:
                out.append(label)
        return out[:8]

    def _competency_public_tags(self, comp_ids: list[str], comp_labels: list[str]) -> list[str]:
        tags: list[str] = []
        for i, slug in enumerate(comp_ids):
            fallback = comp_labels[i] if i < len(comp_labels) else slug
            label = COMPETENCY_PROFILE_TAG_BY_SLUG.get(slug, fallback)
            if label not in tags:
                tags.append(label)
        return tags

    def _animal_types(self, raw: str | None) -> tuple[list[str], list[str]]:
        ids = parse_json_list(raw)
        if not ids:
            return [], []
        labels = [_ANIMAL_LABELS.get(i, i) for i in ids]
        return ids, labels

    @staticmethod
    def _hero_experience_badges(completed: int, profile) -> list[str]:
        n = int(completed or 0)
        has_vet = bool(getattr(profile, "has_veterinary_education", False))
        legacy = (profile.experience_level or "") if profile else ""
        if not has_vet and legacy == "vet_education":
            has_vet = True
        badges: list[str] = []
        if n <= 5:
            badges.append("Новичок")
        else:
            badges.append("Опытный")
        if has_vet:
            badges.append("Ветеринарное образование")
        return badges

    def _build_logistics(self, profile) -> VolunteerPublicLogistics | None:
        raw_slots = _parse_weekly_raw(getattr(profile, "weekly_availability_json", None))
        by_day: dict[str, list[VolunteerTimeRange]] = {}
        for chunk in raw_slots:
            wd = str(chunk.get("weekday", "")).strip().lower()
            if wd not in WEEKDAY_LABEL_RU:
                continue
            rs = chunk.get("ranges") or []
            if not isinstance(rs, list):
                continue
            tr: list[VolunteerTimeRange] = []
            for r in rs:
                if not isinstance(r, dict):
                    continue
                st, en = r.get("start"), r.get("end")
                if st is None or en is None:
                    continue
                try:
                    tr.append(VolunteerTimeRange.model_validate({"start": str(st), "end": str(en)}))
                except Exception:
                    continue
            if tr:
                by_day[wd] = tr
        schedule: list[VolunteerWeekdayScheduleOut] = []
        for day in WEEKDAY_ORDER:
            rng = by_day.get(day)
            if rng:
                schedule.append(
                    VolunteerWeekdayScheduleOut(
                        weekday=day,
                        weekday_label=WEEKDAY_LABEL_RU[day],
                        ranges=rng,
                    )
                )
        night = bool(getattr(profile, "accepts_night_urgency", False))
        mode = getattr(profile, "travel_area_mode", None)
        tlabel = TRAVEL_AREA_MODE_LABELS.get(mode) if mode else None
        if tlabel is None and bool(getattr(profile, "can_travel_other_area", False)):
            tlabel = TRAVEL_AREA_MODE_LABELS.get("region")
        has_block = bool(schedule) or night or tlabel is not None
        if not has_block:
            return None
        return VolunteerPublicLogistics(
            weekly_schedule=schedule,
            accepts_night_urgency=night,
            night_urgency_label="Ночные выезды" if night else None,
            travel_area_mode=mode,
            travel_area_label=tlabel,
        )

    @staticmethod
    def _viewer_actions(viewer: User | None) -> VolunteerViewerActions:
        if viewer is None or viewer.role != UserRole.ORGANIZATION:
            return VolunteerViewerActions()
        return VolunteerViewerActions(can_write_message=True, can_offer_task=True)

    def _item(self, user, profile) -> VolunteerListItem:
        _, comp_labels = self._competency_slugs_labels_from_profile(profile)
        animal_ids, animal_labels = self._animal_types(profile.animal_types_json)
        exp_id = profile.experience_level
        return VolunteerListItem(
            user_id=user.id,
            full_name=user.full_name,
            avatar_url=self._media_url(profile.avatar_path),
            location_city=profile.location_city,
            experience_level=exp_id,
            experience_level_label=EXPERIENCE_LEVEL_LABELS.get(exp_id) if exp_id else None,
            completed_tasks_count=int(profile.completed_tasks_count or 0),
            is_available=bool(profile.is_available),
            competency_tags=self._competency_tag_pills_from_profile(profile) or comp_labels[:5],
            animal_types=animal_labels or (animal_ids if animal_ids else []),
            travel_radius_km=profile.travel_radius_km,
            availability=profile.availability,
        )

    def list_volunteers(self, filters: VolunteerFilterParams) -> VolunteerListResponse:
        total, rows = self.repo.list_volunteers(filters)
        items = [self._item(u, p) for u, p in rows]
        return VolunteerListResponse(total=total, items=items)

    def get_catalogs(self) -> VolunteerCatalogsResponse:
        cities = self.repo.list_catalogs()
        db_items = self.repo.list_competency_catalog()
        if db_items:
            competencies = [CatalogOption(id=it.slug, label=it.label) for it in db_items]
        else:
            competencies = [CatalogOption(**x) for x in COMPETENCY_OPTIONS]
        help_formats = [CatalogOption(id=k, label=v) for k, v in HELP_FORMAT_LABELS.items()]
        travel_modes = [CatalogOption(id=k, label=v) for k, v in TRAVEL_AREA_MODE_LABELS.items()]
        weekdays = [CatalogOption(id=d, label=WEEKDAY_LABEL_RU[d]) for d in WEEKDAY_ORDER]
        return VolunteerCatalogsResponse(
            cities=cities,
            competencies=competencies,
            experience_levels=[CatalogOption(**x) for x in EXPERIENCE_LEVEL_OPTIONS],
            animal_types=[CatalogOption(**x) for x in ANIMAL_TYPE_FILTER_OPTIONS],
            help_formats=help_formats,
            travel_area_modes=travel_modes,
            weekdays=weekdays,
        )

    def get_volunteer_detail(self, volunteer_id: int, viewer: User | None = None) -> VolunteerDetail:
        row = self.repo.get_volunteer(volunteer_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")
        user, profile = row
        comp_ids, comp_labels = self._competency_slugs_labels_from_profile(profile)
        animal_ids, animal_labels = self._animal_types(profile.animal_types_json)
        completed = int(profile.completed_tasks_count or 0)

        city = (profile.location_city or "").strip() or None
        district = (profile.location_district or "").strip() or None
        if city and district:
            loc_display = f"{city}, {district}"
        else:
            loc_display = city or district

        hf = profile.help_format
        hf_label = HELP_FORMAT_LABELS.get(hf) if hf else None

        logistics = self._build_logistics(profile)
        about = (profile.about_me or "").strip() or None

        articles_db = self.repo.list_published_articles_by_volunteer(user.id)
        articles = [
            VolunteerPublicArticleCard(
                id=a.id,
                title=a.title,
                summary=a.summary,
                read_minutes=int(a.read_minutes or 5),
                category=a.category,
                category_label=KNOWLEDGE_CATEGORY_LABELS.get(a.category, a.category),
            )
            for a in articles_db
        ]

        avail = bool(profile.is_available)
        readiness_status: str = "available" if avail else "paused"
        readiness_label = "Готов к задачам" if avail else "Временно не беру задачи"

        competency_tags = self._competency_public_tags(comp_ids, comp_labels)

        return VolunteerDetail(
            user_id=user.id,
            full_name=user.full_name,
            avatar_url=self._media_url(profile.avatar_path),
            completed_tasks_count=completed,
            readiness_status=readiness_status,
            readiness_label=readiness_label,
            hero_experience_badges=self._hero_experience_badges(completed, profile),
            location_city=city,
            location_district=district,
            location_display=loc_display,
            help_format=hf,
            help_format_label=hf_label,
            competency_slugs=comp_ids,
            competency_tags=competency_tags,
            animal_category_ids=animal_ids,
            animal_category_labels=animal_labels,
            logistics=logistics,
            about_me=about,
            articles=articles,
            viewer=self._viewer_actions(viewer),
            travel_radius_km=profile.travel_radius_km,
        )

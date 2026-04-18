from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.animals.jsonutil import parse_json_list
from app.modules.volunteers.constants import (
    ANIMAL_TYPE_FILTER_OPTIONS,
    COMPETENCY_OPTIONS,
    COMPETENCY_SHORT_LABELS,
    EXPERIENCE_LEVEL_LABELS,
    EXPERIENCE_LEVEL_OPTIONS,
)
from app.modules.volunteers.repository import VolunteerRepository
from app.modules.volunteers.schemas import (
    CatalogOption,
    VolunteerCatalogsResponse,
    VolunteerDetail,
    VolunteerFilterParams,
    VolunteerListItem,
    VolunteerListResponse,
    VolunteerReviewItem,
)

_ANIMAL_LABELS = {x["id"]: x["label"] for x in ANIMAL_TYPE_FILTER_OPTIONS if x["id"] != "all"}
_COMP_FULL = {x["id"]: x["label"] for x in COMPETENCY_OPTIONS}


class VolunteerService:
    def __init__(self, repo: VolunteerRepository):
        self.repo = repo

    def _media_url(self, path: str | None) -> str | None:
        if not path:
            return None
        return f"{settings.media_url_prefix}/{path}"

    def _competency_tag_pills(self, raw: str | None) -> list[str]:
        ids = parse_json_list(raw)
        out: list[str] = []
        for cid in ids:
            label = COMPETENCY_SHORT_LABELS.get(cid) or _COMP_FULL.get(cid) or cid
            if label not in out:
                out.append(label)
        return out[:8]

    def _competency_full_labels(self, raw: str | None) -> tuple[list[str], list[str]]:
        ids = parse_json_list(raw)
        labels = [_COMP_FULL.get(i, i) for i in ids]
        return ids, labels

    def _animal_types(self, raw: str | None) -> tuple[list[str], list[str]]:
        ids = parse_json_list(raw)
        if not ids:
            return [], []
        labels = [_ANIMAL_LABELS.get(i, i) for i in ids]
        return ids, labels

    def _item(self, user, profile) -> VolunteerListItem:
        _, comp_labels = self._competency_full_labels(profile.competencies_json)
        animal_ids, animal_labels = self._animal_types(profile.animal_types_json)
        exp_id = profile.experience_level
        return VolunteerListItem(
            user_id=user.id,
            full_name=user.full_name,
            avatar_url=self._media_url(profile.avatar_path),
            rating=float(profile.rating or 0.0),
            location_city=profile.location_city,
            experience_level=exp_id,
            experience_level_label=EXPERIENCE_LEVEL_LABELS.get(exp_id) if exp_id else None,
            completed_tasks_count=int(profile.completed_tasks_count or 0),
            is_available=bool(profile.is_available),
            competency_tags=self._competency_tag_pills(profile.competencies_json) or comp_labels[:5],
            animal_types=animal_labels or (animal_ids if animal_ids else []),
            travel_radius_km=profile.travel_radius_km,
            availability=profile.availability,
            skills=profile.skills,
            experience=profile.experience,
            preferred_help_format=profile.preferred_help_format,
            animal_categories=profile.animal_categories,
        )

    def list_volunteers(self, filters: VolunteerFilterParams) -> VolunteerListResponse:
        total, rows = self.repo.list_volunteers(filters)
        items = [self._item(u, p) for u, p in rows]
        return VolunteerListResponse(total=total, items=items)

    def get_catalogs(self) -> VolunteerCatalogsResponse:
        cities = self.repo.list_catalogs()
        return VolunteerCatalogsResponse(
            cities=cities,
            competencies=[CatalogOption(**x) for x in COMPETENCY_OPTIONS],
            experience_levels=[CatalogOption(**x) for x in EXPERIENCE_LEVEL_OPTIONS],
            animal_types=[CatalogOption(**x) for x in ANIMAL_TYPE_FILTER_OPTIONS],
        )

    def get_volunteer_detail(self, volunteer_id: int) -> VolunteerDetail:
        row = self.repo.get_volunteer(volunteer_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")
        user, profile = row
        comp_ids, comp_labels = self._competency_full_labels(profile.competencies_json)
        animal_ids, animal_labels = self._animal_types(profile.animal_types_json)
        reviews_db = self.repo.list_reviews(volunteer_id)
        reviews = [
            VolunteerReviewItem(
                author_name=r.author_name,
                author_avatar_url=self._media_url(r.author_avatar_path),
                review_date=r.review_date,
                rating=r.rating,
                text=r.text,
            )
            for r in reviews_db
        ]
        exp_id = profile.experience_level
        return VolunteerDetail(
            user_id=user.id,
            full_name=user.full_name,
            avatar_url=self._media_url(profile.avatar_path),
            rating=float(profile.rating or 0.0),
            location_city=profile.location_city,
            travel_radius_km=profile.travel_radius_km,
            competencies=comp_ids,
            competency_labels=comp_labels,
            about_me=profile.about_me or profile.experience,
            animal_types=animal_ids,
            animal_type_labels=animal_labels,
            availability=profile.availability,
            completed_tasks_count=int(profile.completed_tasks_count or 0),
            experience_level=exp_id,
            experience_level_label=EXPERIENCE_LEVEL_LABELS.get(exp_id) if exp_id else None,
            is_available=bool(profile.is_available),
            reviews=reviews,
        )

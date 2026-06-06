import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole
from app.modules.knowledge.hints import build_help_request_knowledge_hints
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import KB_CATEGORY_OPTIONS, KnowledgeHintItem
from app.modules.urgent.repository import UrgentRepository
from app.modules.urgent.service import UrgentService
from app.modules.volunteers.matching import (
    VolunteerMatchContext,
    score_volunteer_task,
    sort_scored_tasks,
)
from app.modules.volunteers.schemas import (
    VolunteerCompletedTaskItem,
    VolunteerCompletedTasksResponse,
    VolunteerTaskFeedItem,
    VolunteerTaskFeedResponse,
)
from app.modules.volunteers.task_feed_repository import VolunteerTaskFeedRepository

_CATEGORY_LABELS = {x["id"]: x["label"] for x in KB_CATEGORY_OPTIONS}


def _cover_url(path: str | None) -> str | None:
    if not path or not str(path).strip():
        return None
    return f"{settings.media_url_prefix}/{str(path).strip().lstrip('/')}"


_MATCH_REASON_LABELS: dict[str, str] = {
    "nearby": "Рядом с вами",
    "same_city": "В вашем городе",
    "location_unknown": "Локация не указана",
    "skills_match": "Подходит по навыкам",
    "general_skills": "Соответствует вашим навыкам",
    "urgent": "Срочная заявка",
    "deadline_soon": "Дедлайн в ближайшие сутки",
    "deadline_week": "Дедлайн на этой неделе",
    "similar_experience": "Похожий опыт выполнения",
    "known_organization": "Вы уже помогали этой организации",
    "availability_set": "Указана доступность",
}


class VolunteerTaskFeedService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VolunteerTaskFeedRepository(db)
        self.urgent = UrgentService(UrgentRepository(db))
        self._knowledge_repo = KnowledgeRepository(db)
        self._hint_articles: list | None = None

    def _context_tip_articles(self):
        if self._hint_articles is None:
            self._hint_articles = self._knowledge_repo.list_context_tip_candidates()
        return self._hint_articles

    def _knowledge_hints_for_request(self, req, required_competencies: list[str]) -> list[KnowledgeHintItem]:
        picked = build_help_request_knowledge_hints(
            req,
            required_competencies=required_competencies,
            articles=self._context_tip_articles(),
            limit=2,
        )
        return [
            KnowledgeHintItem(
                id=row.article.id,
                title=row.article.title,
                summary=row.article.summary,
                cover_url=_cover_url(row.article.cover_path),
                category=row.article.category,
                category_label=_CATEGORY_LABELS.get(row.article.category),
                read_minutes=row.article.read_minutes,
                match_score=row.score,
                match_reasons=list(row.reasons),
            )
            for row in picked
        ]

    def _build_context(self, user: User) -> VolunteerMatchContext:
        profile = user.volunteer_profile
        if profile is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Профиль волонтёра не найден")

        slugs: set[str] = set()
        for assignment in profile.competency_assignments or []:
            item = assignment.competency_item
            if item and item.slug:
                slugs.add(str(item.slug).strip().lower())

        has_weekly = False
        raw = profile.weekly_availability_json
        if raw:
            try:
                data = json.loads(raw)
                has_weekly = isinstance(data, list) and len(data) > 0
            except (json.JSONDecodeError, TypeError):
                has_weekly = False

        completed_types, completed_orgs = self.repo.completed_task_history(user.id)

        return VolunteerMatchContext(
            competency_slugs=frozenset(slugs),
            latitude=profile.latitude,
            longitude=profile.longitude,
            travel_radius_km=profile.travel_radius_km,
            location_city=profile.location_city,
            is_available=bool(profile.is_available),
            accepts_night_urgency=bool(profile.accepts_night_urgency),
            completed_help_types=frozenset(completed_types),
            completed_org_ids=frozenset(completed_orgs),
            has_weekly_schedule=has_weekly,
        )

    def list_personalized_feed(
        self,
        user: User,
        *,
        q: str | None,
        limit: int,
        offset: int,
    ) -> VolunteerTaskFeedResponse:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")

        loaded = self.repo.get_volunteer_user(user.id)
        if loaded is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

        profile = loaded.volunteer_profile
        if profile is not None:
            self.db.expire(profile, ["competency_assignments"])

        ctx = self._build_context(loaded)
        completed_count = self.repo.count_completed_tasks(user.id)

        if not ctx.is_available:
            return VolunteerTaskFeedResponse(
                total=0,
                items=[],
                is_available=False,
                completed_tasks_count=completed_count,
                message="В профиле отключена доступность — включите «готов помогать», чтобы видеть задачи",
            )

        candidates = self.repo.list_open_volunteer_tasks(user.id, q)
        scored: list = []
        for req in candidates:
            item = score_volunteer_task(ctx, req)
            if item is not None:
                scored.append(item)

        ordered = sort_scored_tasks(scored)
        total = len(ordered)
        page = ordered[offset : offset + limit]

        items: list[VolunteerTaskFeedItem] = []
        for row in page:
            base = self.urgent._to_item(row.request)
            req = row.request
            lat, lon = req.latitude, req.longitude
            if (lat is None or lon is None) and req.organization is not None:
                org = req.organization
                if org.latitude is not None and org.longitude is not None:
                    lat, lon = org.latitude, org.longitude
            items.append(
                VolunteerTaskFeedItem(
                    **base.model_dump(),
                    address=req.address,
                    latitude=lat,
                    longitude=lon,
                    match_score=row.match_score,
                    match_reasons=list(row.match_reasons),
                    match_reason_labels=[_MATCH_REASON_LABELS.get(r, r) for r in row.match_reasons],
                    distance_km=row.distance_km,
                    required_competencies=list(row.required_competencies),
                    knowledge_hints=self._knowledge_hints_for_request(row.request, list(row.required_competencies)),
                )
            )

        return VolunteerTaskFeedResponse(
            total=total,
            items=items,
            is_available=True,
            completed_tasks_count=completed_count,
            message=None,
        )

    def list_completed_tasks(
        self,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> VolunteerCompletedTasksResponse:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")

        total, rows = self.repo.list_completed_tasks(user.id, limit, offset)
        items: list[VolunteerCompletedTaskItem] = []
        for row in rows:
            hr = row.help_request
            org = hr.organization if hr else None
            completed_at = row.updated_at or row.created_at
            items.append(
                VolunteerCompletedTaskItem(
                    response_id=row.id,
                    completed_at=completed_at,
                    help_request_id=hr.id if hr else 0,
                    title=hr.title if hr else "",
                    organization_id=org.id if org else None,
                    organization_name=org.name if org else None,
                    help_type=hr.help_type if hr else "",
                    city=hr.city if hr else None,
                    is_urgent=bool(hr.is_urgent) if hr else False,
                )
            )

        return VolunteerCompletedTasksResponse(
            total=total,
            completed_tasks_count=self.repo.count_completed_tasks(user.id),
            items=items,
        )

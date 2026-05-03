import json
from datetime import datetime

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.help_request import HelpRequest
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.modules.urgent.repository import UrgentRepository
from app.modules.urgent.schemas import (
    HELP_TYPE_OPTIONS,
    CatalogOption,
    UrgentCatalogsResponse,
    UrgentFilterParams,
    UrgentListResponse,
    UrgentRequestCreate,
    UrgentRequestDetail,
    UrgentRequestListItem,
    UrgentRequestUpdate,
)

_HELP_TYPE_LABEL = {x["id"]: x["label"] for x in HELP_TYPE_OPTIONS}


class UrgentService:
    def __init__(self, repo: UrgentRepository):
        self.repo = repo

    def _organization_for_user(self, user: User) -> Organization:
        if user.role != UserRole.ORGANIZATION:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization role required")
        org = (
            self.repo.db.query(Organization)
            .filter(Organization.owner_user_id == user.id)
            .order_by(Organization.id.asc())
            .first()
        )
        if org is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization profile not found")
        return org

    @staticmethod
    def _deadline_label(deadline_at: datetime | None, deadline_note: str | None) -> str | None:
        if deadline_note is not None and deadline_note.strip():
            return deadline_note.strip()
        if deadline_at is None:
            return None
        now = datetime.utcnow()
        if deadline_at.date() == now.date():
            return f"Сегодня до {deadline_at.strftime('%H:%M')}"
        return deadline_at.strftime("До %d.%m %H:%M")

    @staticmethod
    def _primary_photo_url(req: HelpRequest) -> str | None:
        if req.animal is None or not req.animal.photos:
            return f"{settings.media_url_prefix}/{req.media_path}" if req.media_path else None
        primary = next((p for p in req.animal.photos if p.is_primary), None) or req.animal.photos[0]
        return f"{settings.media_url_prefix}/{primary.file_path}"

    def _to_item(self, req: HelpRequest) -> UrgentRequestListItem:
        badges: list[str] = []
        if req.is_urgent:
            badges.append("срочно")
        badges.append(_HELP_TYPE_LABEL.get(req.help_type, req.help_type))
        if req.volunteer_needed:
            badges.append("нужен волонтер")
        return UrgentRequestListItem(
            id=req.id,
            title=req.title,
            description=req.description,
            city=req.city,
            organization_id=req.organization_id,
            organization_name=req.organization.name if req.organization else "Организация",
            animal_id=req.animal_id,
            animal_name=req.animal.name if req.animal else None,
            animal_species=req.animal.species if req.animal else None,
            help_type=req.help_type,
            is_urgent=bool(req.is_urgent),
            volunteer_needed=bool(req.volunteer_needed),
            deadline_at=req.deadline_at,
            deadline_note=req.deadline_note,
            deadline_label=self._deadline_label(req.deadline_at, req.deadline_note),
            status=req.status,
            target_amount=req.target_amount,
            primary_photo_url=self._primary_photo_url(req),
            badges=badges,
        )

    def _to_detail(self, req: HelpRequest) -> UrgentRequestDetail:
        item = self._to_item(req)
        comps: list[str] = []
        if req.volunteer_competencies_json:
            try:
                raw = json.loads(req.volunteer_competencies_json)
                if isinstance(raw, list):
                    comps = [str(x) for x in raw]
            except json.JSONDecodeError:
                comps = []
        return UrgentRequestDetail(
            **item.model_dump(),
            address=req.address,
            latitude=req.latitude,
            longitude=req.longitude,
            volunteer_requirements=req.volunteer_requirements,
            volunteer_competencies=comps,
            media_url=f"{settings.media_url_prefix}/{req.media_path}" if req.media_path else None,
            created_at=req.created_at,
            updated_at=req.updated_at,
        )

    def list_urgent(self, filters: UrgentFilterParams) -> UrgentListResponse:
        total, rows = self.repo.list_public_urgent(filters)
        return UrgentListResponse(total=total, items=[self._to_item(r) for r in rows])

    def get_catalogs(self) -> UrgentCatalogsResponse:
        cities, species = self.repo.list_catalogs()
        return UrgentCatalogsResponse(
            cities=cities,
            species=[CatalogOption(id="all", label="Все")] + [CatalogOption(id=s, label=s) for s in species],
            help_types=[CatalogOption(**x) for x in HELP_TYPE_OPTIONS],
            statuses=[
                CatalogOption(id="open", label="Открыта"),
                CatalogOption(id="in_progress", label="В работе"),
                CatalogOption(id="closed", label="Закрыта"),
            ],
        )

    def get_detail(self, request_id: int) -> UrgentRequestDetail:
        req = self.repo.get_request(request_id)
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help request not found")
        return self._to_detail(req)

    def create_request(self, user: User, payload: UrgentRequestCreate) -> UrgentRequestDetail:
        org = self._organization_for_user(user)
        if payload.animal_id is not None:
            animal = self.repo.get_animal(payload.animal_id)
            if animal is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")
            if animal.organization_id != org.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Animal must belong to same organization",
                )
        req = HelpRequest(
            organization_id=org.id,
            animal_id=payload.animal_id,
            title=payload.title,
            description=payload.description,
            city=payload.city,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            help_type=payload.help_type,
            is_urgent=payload.is_urgent,
            volunteer_needed=payload.volunteer_needed,
            volunteer_requirements=payload.volunteer_requirements,
            volunteer_competencies_json=json.dumps(payload.volunteer_competencies, ensure_ascii=False),
            target_amount=payload.target_amount,
            deadline_at=payload.deadline_at,
            deadline_note=payload.deadline_note,
            media_path=payload.media_path,
            status=payload.status,
            is_published=payload.is_published,
            is_archived=False,
        )
        self.repo.db.add(req)
        self.repo.db.commit()
        return self.get_detail(req.id)

    def update_request(self, request_id: int, user: User, payload: UrgentRequestUpdate) -> UrgentRequestDetail:
        org = self._organization_for_user(user)
        req = self.repo.get_request_for_owner(request_id)
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help request not found")
        if req.organization_id != org.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only manage own help requests")
        if payload.animal_id is not None:
            animal = self.repo.get_animal(payload.animal_id)
            if animal is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")
            if animal.organization_id != req.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Animal must belong to same organization",
                )
            req.animal_id = payload.animal_id

        for field in (
            "title",
            "description",
            "city",
            "address",
            "latitude",
            "longitude",
            "help_type",
            "is_urgent",
            "volunteer_needed",
            "volunteer_requirements",
            "target_amount",
            "deadline_at",
            "deadline_note",
            "media_path",
            "status",
            "is_published",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(req, field, value)
        if payload.volunteer_competencies is not None:
            req.volunteer_competencies_json = json.dumps(payload.volunteer_competencies, ensure_ascii=False)
        self.repo.db.commit()
        return self.get_detail(req.id)

    def close_request(self, request_id: int, user: User) -> UrgentRequestDetail:
        org = self._organization_for_user(user)
        req = self.repo.get_request_for_owner(request_id)
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help request not found")
        if req.organization_id != org.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only manage own help requests")
        req.status = "closed"
        self.repo.db.commit()
        self.repo.db.refresh(req)
        return self._to_detail(req)

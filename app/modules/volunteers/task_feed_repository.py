from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.animal import Animal
from app.models.help_request import HelpRequest
from app.models.profile import VolunteerProfile
from app.models.user import User
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.models.volunteer_help_response import VolunteerHelpResponse, VolunteerHelpResponseStatus


class VolunteerTaskFeedRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_volunteer_user(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .options(
                joinedload(User.volunteer_profile)
                .joinedload(VolunteerProfile.competency_assignments)
                .joinedload(VolunteerCompetencyAssignment.competency_item)
            )
            .filter(User.id == user_id)
            .first()
        )

    def list_open_volunteer_tasks(self, volunteer_user_id: int, q: str | None = None) -> list[HelpRequest]:
        responded_ids = (
            self.db.query(VolunteerHelpResponse.help_request_id)
            .filter(VolunteerHelpResponse.volunteer_user_id == volunteer_user_id)
            .subquery()
        )
        query = (
            self.db.query(HelpRequest)
            .options(
                joinedload(HelpRequest.organization),
                joinedload(HelpRequest.animal).joinedload(Animal.photos),
            )
            .filter(
                HelpRequest.is_archived.is_(False),
                HelpRequest.is_published.is_(True),
                HelpRequest.volunteer_needed.is_(True),
                HelpRequest.status.in_(("open", "in_progress")),
                ~HelpRequest.id.in_(responded_ids),
            )
        )
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(HelpRequest.title).like(like),
                    func.lower(HelpRequest.description).like(like),
                )
            )
        return query.order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc()).limit(500).all()

    def completed_task_history(self, volunteer_user_id: int) -> tuple[set[str], set[int]]:
        rows = (
            self.db.query(HelpRequest.help_type, HelpRequest.organization_id)
            .join(VolunteerHelpResponse, VolunteerHelpResponse.help_request_id == HelpRequest.id)
            .filter(
                VolunteerHelpResponse.volunteer_user_id == volunteer_user_id,
                VolunteerHelpResponse.status == VolunteerHelpResponseStatus.COMPLETED.value,
            )
            .all()
        )
        help_types: set[str] = set()
        org_ids: set[int] = set()
        for help_type, org_id in rows:
            if help_type:
                help_types.add(str(help_type).strip().lower())
            if org_id is not None:
                org_ids.add(int(org_id))
        return help_types, org_ids

    def count_completed_tasks(self, volunteer_user_id: int) -> int:
        return int(
            self.db.query(VolunteerHelpResponse.id)
            .filter(
                VolunteerHelpResponse.volunteer_user_id == volunteer_user_id,
                VolunteerHelpResponse.status == VolunteerHelpResponseStatus.COMPLETED.value,
            )
            .count()
            or 0
        )

    def list_completed_tasks(
        self, volunteer_user_id: int, limit: int, offset: int
    ) -> tuple[int, list[VolunteerHelpResponse]]:
        base = (
            self.db.query(VolunteerHelpResponse)
            .options(
                joinedload(VolunteerHelpResponse.help_request).joinedload(HelpRequest.organization),
            )
            .filter(
                VolunteerHelpResponse.volunteer_user_id == volunteer_user_id,
                VolunteerHelpResponse.status == VolunteerHelpResponseStatus.COMPLETED.value,
            )
        )
        total = int(base.order_by(None).count() or 0)
        rows = (
            base.order_by(VolunteerHelpResponse.updated_at.desc(), VolunteerHelpResponse.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, rows

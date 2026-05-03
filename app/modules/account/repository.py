from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.adoption_application import AnimalAdoptionApplication
from app.models.animal import Animal
from app.models.help_request import HelpRequest
from app.models.profile import UserProfile, VolunteerProfile
from app.models.user import User
from app.models.volunteer_competency import VolunteerCompetencyAssignment
from app.models.volunteer_help_response import VolunteerHelpResponse, VolunteerHelpResponseStatus


class AccountRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_me(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .options(
                joinedload(User.user_profile),
                joinedload(User.volunteer_profile)
                .selectinload(VolunteerProfile.competency_assignments)
                .selectinload(VolunteerCompetencyAssignment.competency_item),
            )
            .filter(User.id == user_id)
            .first()
        )

    def get_or_create_user_profile(self, user_id: int) -> UserProfile:
        row = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if row:
            return row
        row = UserProfile(user_id=user_id)
        self.db.add(row)
        self.db.flush()
        return row

    def count_applications(self, user_id: int, search: str | None) -> int:
        if search and search.strip():
            like = f"%{search.strip().lower()}%"
            cnt = (
                self.db.query(func.count(AnimalAdoptionApplication.id))
                .select_from(AnimalAdoptionApplication)
                .join(Animal, Animal.id == AnimalAdoptionApplication.animal_id)
                .filter(
                    AnimalAdoptionApplication.user_id == user_id,
                    func.lower(Animal.name).like(like),
                )
                .scalar()
            )
        else:
            cnt = (
                self.db.query(func.count(AnimalAdoptionApplication.id))
                .filter(AnimalAdoptionApplication.user_id == user_id)
                .scalar()
            )
        return int(cnt or 0)

    def list_applications(self, user_id: int, search: str | None, limit: int, offset: int) -> list:
        q = (
            self.db.query(AnimalAdoptionApplication)
            .options(
                joinedload(AnimalAdoptionApplication.animal).joinedload(Animal.photos),
                joinedload(AnimalAdoptionApplication.animal).joinedload(Animal.organization),
            )
            .filter(AnimalAdoptionApplication.user_id == user_id)
        )
        if search and search.strip():
            like = f"%{search.strip().lower()}%"
            q = q.join(Animal, Animal.id == AnimalAdoptionApplication.animal_id).filter(
                func.lower(Animal.name).like(like)
            )
        return (
            q.order_by(AnimalAdoptionApplication.created_at.desc()).offset(offset).limit(limit).all()
        )

    def get_application(self, application_id: int, user_id: int) -> AnimalAdoptionApplication | None:
        return (
            self.db.query(AnimalAdoptionApplication)
            .options(
                joinedload(AnimalAdoptionApplication.animal).joinedload(Animal.photos),
                joinedload(AnimalAdoptionApplication.animal).joinedload(Animal.organization),
            )
            .filter(AnimalAdoptionApplication.id == application_id, AnimalAdoptionApplication.user_id == user_id)
            .first()
        )

    def get_application_by_user_animal(self, user_id: int, animal_id: int) -> AnimalAdoptionApplication | None:
        return (
            self.db.query(AnimalAdoptionApplication)
            .filter(
                AnimalAdoptionApplication.user_id == user_id,
                AnimalAdoptionApplication.animal_id == animal_id,
            )
            .first()
        )

    def get_animal(self, animal_id: int) -> Animal | None:
        return (
            self.db.query(Animal)
            .options(joinedload(Animal.organization), joinedload(Animal.photos))
            .filter(Animal.id == animal_id)
            .first()
        )

    @staticmethod
    def _volunteer_responses_tab_filter(q, tab: str):
        t = tab.strip().lower()
        if t in ("", "all"):
            return q
        if t == "pending":
            return q.filter(VolunteerHelpResponse.status == VolunteerHelpResponseStatus.PENDING.value)
        if t == "in_progress":
            return q.filter(VolunteerHelpResponse.status == VolunteerHelpResponseStatus.ACCEPTED.value)
        if t == "completed":
            return q.filter(VolunteerHelpResponse.status == VolunteerHelpResponseStatus.COMPLETED.value)
        if t == "archive":
            return q.filter(
                VolunteerHelpResponse.status.in_(
                    (
                        VolunteerHelpResponseStatus.REJECTED.value,
                        VolunteerHelpResponseStatus.WITHDRAWN.value,
                    )
                )
            )
        return q

    def count_volunteer_responses(self, volunteer_user_id: int, search: str | None, tab: str) -> int:
        q = self.db.query(VolunteerHelpResponse).filter(
            VolunteerHelpResponse.volunteer_user_id == volunteer_user_id
        )
        q = self._volunteer_responses_tab_filter(q, tab)
        if search and search.strip():
            like = f"%{search.strip().lower()}%"
            q = q.join(HelpRequest, HelpRequest.id == VolunteerHelpResponse.help_request_id).filter(
                or_(func.lower(HelpRequest.title).like(like), func.lower(HelpRequest.description).like(like))
            )
        return q.count()

    def list_volunteer_responses(
        self, volunteer_user_id: int, search: str | None, tab: str, limit: int, offset: int
    ) -> list:
        q = (
            self.db.query(VolunteerHelpResponse)
            .options(
                joinedload(VolunteerHelpResponse.help_request).joinedload(HelpRequest.organization),
                joinedload(VolunteerHelpResponse.report),
            )
            .filter(VolunteerHelpResponse.volunteer_user_id == volunteer_user_id)
        )
        q = self._volunteer_responses_tab_filter(q, tab)
        if search and search.strip():
            like = f"%{search.strip().lower()}%"
            q = q.join(HelpRequest, HelpRequest.id == VolunteerHelpResponse.help_request_id).filter(
                or_(func.lower(HelpRequest.title).like(like), func.lower(HelpRequest.description).like(like))
            )
        return q.order_by(VolunteerHelpResponse.created_at.desc()).offset(offset).limit(limit).all()

    def get_volunteer_response(self, response_id: int, volunteer_user_id: int) -> VolunteerHelpResponse | None:
        return (
            self.db.query(VolunteerHelpResponse)
            .options(
                joinedload(VolunteerHelpResponse.help_request).joinedload(HelpRequest.organization),
                joinedload(VolunteerHelpResponse.report),
            )
            .filter(
                VolunteerHelpResponse.id == response_id,
                VolunteerHelpResponse.volunteer_user_id == volunteer_user_id,
            )
            .first()
        )

    def get_volunteer_response_by_pair(
        self, volunteer_user_id: int, help_request_id: int
    ) -> VolunteerHelpResponse | None:
        return (
            self.db.query(VolunteerHelpResponse)
            .filter(
                VolunteerHelpResponse.volunteer_user_id == volunteer_user_id,
                VolunteerHelpResponse.help_request_id == help_request_id,
            )
            .first()
        )

    def get_help_request(self, help_request_id: int) -> HelpRequest | None:
        return (
            self.db.query(HelpRequest)
            .options(joinedload(HelpRequest.organization))
            .filter(HelpRequest.id == help_request_id)
            .first()
        )

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.adoption_application import AnimalAdoptionApplication
from app.models.animal import Animal
from app.models.animal_catalog import AnimalCatalogAssignment, AnimalCatalogItem
from app.models.help_request import HelpRequest
from app.models.org_chat import OrgChatDialog, OrgChatMessage
from app.models.event import Event
from app.models.knowledge import KnowledgeArticle
from app.models.organization import Organization
from app.models.organization_home_story import OrganizationHomeStory
from app.models.organization_report import OrganizationReport
from app.models.profile import UserProfile, VolunteerProfile
from app.models.user import User, UserRole
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

    def get_owned_organization(self, owner_user_id: int):
        from app.models.organization import Organization

        return (
            self.db.query(Organization)
            .filter(Organization.owner_user_id == owner_user_id)
            .order_by(Organization.id.asc())
            .first()
        )

    def _org_animals_query(self, organization_id: int, q: str | None, tab: str):
        query = self.db.query(Animal).filter(Animal.organization_id == organization_id)
        if tab == "archive":
            query = query.filter(Animal.status == "archived")
        else:
            query = query.filter(Animal.status != "archived")
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(func.lower(Animal.name).like(like))
        return query

    def count_org_animals(self, organization_id: int, q: str | None, tab: str = "active") -> int:
        return int(self._org_animals_query(organization_id, q, tab).count() or 0)

    def list_org_animals(
        self, organization_id: int, q: str | None, limit: int, offset: int, tab: str = "active"
    ) -> list[Animal]:
        return (
            self._org_animals_query(organization_id, q, tab)
            .options(
                joinedload(Animal.photos),
                selectinload(Animal.catalog_assignments).selectinload(AnimalCatalogAssignment.catalog_item),
            )
            .order_by(Animal.created_at.desc(), Animal.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_org_animal(self, organization_id: int, animal_id: int) -> Animal | None:
        return (
            self.db.query(Animal)
            .options(
                joinedload(Animal.photos),
                selectinload(Animal.catalog_assignments).selectinload(AnimalCatalogAssignment.catalog_item),
            )
            .filter(Animal.organization_id == organization_id, Animal.id == animal_id)
            .first()
        )

    def set_animal_catalog_slugs(
        self, animal_id: int, health_care_slugs: list[str], character_slugs: list[str]
    ) -> None:
        key_to_id = {(r.kind, r.slug): int(r.id) for r in self.db.query(AnimalCatalogItem).all()}

        def replace_kind(kind: str, slugs: list[str]) -> None:
            ids_for_kind = [cid for (k, _), cid in key_to_id.items() if k == kind]
            if ids_for_kind:
                self.db.query(AnimalCatalogAssignment).filter(
                    AnimalCatalogAssignment.animal_id == animal_id,
                    AnimalCatalogAssignment.catalog_item_id.in_(ids_for_kind),
                ).delete(synchronize_session=False)
            seen: set[str] = set()
            for raw in slugs:
                slug = (raw or "").strip().lower()
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                cid = key_to_id.get((kind, slug))
                if cid is not None:
                    self.db.add(AnimalCatalogAssignment(animal_id=animal_id, catalog_item_id=cid))

        replace_kind("health_care", health_care_slugs)
        replace_kind("character", character_slugs)

    def count_org_help_requests(self, organization_id: int, q: str | None, type_group: str | None) -> int:
        query = self.db.query(HelpRequest).filter(HelpRequest.organization_id == organization_id)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(HelpRequest.title).like(like),
                    func.lower(HelpRequest.description).like(like),
                )
            )
        if type_group == "fundraising":
            query = query.filter(HelpRequest.help_type.in_(("financial", "food", "medical")))
        elif type_group == "volunteer_task":
            query = query.filter(~HelpRequest.help_type.in_(("financial", "food", "medical")))
        return int(query.count() or 0)

    def list_org_help_requests(
        self, organization_id: int, q: str | None, type_group: str | None, limit: int, offset: int
    ) -> list[HelpRequest]:
        query = (
            self.db.query(HelpRequest)
            .options(
                joinedload(HelpRequest.organization),
                joinedload(HelpRequest.animal).joinedload(Animal.photos),
            )
            .filter(HelpRequest.organization_id == organization_id)
        )
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(HelpRequest.title).like(like),
                    func.lower(HelpRequest.description).like(like),
                )
            )
        if type_group == "fundraising":
            query = query.filter(HelpRequest.help_type.in_(("financial", "food", "medical")))
        elif type_group == "volunteer_task":
            query = query.filter(~HelpRequest.help_type.in_(("financial", "food", "medical")))
        return (
            query.order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_org_adoption_applications(self, organization_id: int, q: str | None, status_value: str | None) -> int:
        query = (
            self.db.query(AnimalAdoptionApplication)
            .join(Animal, Animal.id == AnimalAdoptionApplication.animal_id)
            .join(User, User.id == AnimalAdoptionApplication.user_id)
            .filter(Animal.organization_id == organization_id)
        )
        if status_value and status_value != "all":
            query = query.filter(AnimalAdoptionApplication.status == status_value)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(Animal.name).like(like),
                )
            )
        return int(query.count() or 0)

    def list_org_adoption_applications(
        self, organization_id: int, q: str | None, status_value: str | None, limit: int, offset: int
    ) -> list[AnimalAdoptionApplication]:
        query = (
            self.db.query(AnimalAdoptionApplication)
            .options(
                joinedload(AnimalAdoptionApplication.user),
                joinedload(AnimalAdoptionApplication.animal),
            )
            .join(Animal, Animal.id == AnimalAdoptionApplication.animal_id)
            .join(User, User.id == AnimalAdoptionApplication.user_id)
            .filter(Animal.organization_id == organization_id)
        )
        if status_value and status_value != "all":
            query = query.filter(AnimalAdoptionApplication.status == status_value)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(Animal.name).like(like),
                )
            )
        return (
            query.order_by(AnimalAdoptionApplication.created_at.desc(), AnimalAdoptionApplication.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_org_adoption_application(
        self, organization_id: int, application_id: int
    ) -> AnimalAdoptionApplication | None:
        return (
            self.db.query(AnimalAdoptionApplication)
            .options(
                joinedload(AnimalAdoptionApplication.user),
                joinedload(AnimalAdoptionApplication.animal),
            )
            .join(Animal, Animal.id == AnimalAdoptionApplication.animal_id)
            .filter(
                Animal.organization_id == organization_id,
                AnimalAdoptionApplication.id == application_id,
            )
            .first()
        )

    def count_org_volunteer_responses(self, organization_id: int, q: str | None, status_value: str | None) -> int:
        query = (
            self.db.query(VolunteerHelpResponse)
            .join(HelpRequest, HelpRequest.id == VolunteerHelpResponse.help_request_id)
            .join(User, User.id == VolunteerHelpResponse.volunteer_user_id)
            .filter(HelpRequest.organization_id == organization_id)
        )
        if status_value and status_value != "all":
            query = query.filter(VolunteerHelpResponse.status == status_value)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(HelpRequest.title).like(like),
                )
            )
        return int(query.count() or 0)

    def list_org_volunteer_responses(
        self, organization_id: int, q: str | None, status_value: str | None, limit: int, offset: int
    ) -> list[VolunteerHelpResponse]:
        query = (
            self.db.query(VolunteerHelpResponse)
            .options(
                joinedload(VolunteerHelpResponse.volunteer),
                joinedload(VolunteerHelpResponse.help_request),
            )
            .join(HelpRequest, HelpRequest.id == VolunteerHelpResponse.help_request_id)
            .join(User, User.id == VolunteerHelpResponse.volunteer_user_id)
            .filter(HelpRequest.organization_id == organization_id)
        )
        if status_value and status_value != "all":
            query = query.filter(VolunteerHelpResponse.status == status_value)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(HelpRequest.title).like(like),
                )
            )
        return (
            query.order_by(VolunteerHelpResponse.created_at.desc(), VolunteerHelpResponse.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_org_volunteer_response(self, organization_id: int, response_id: int) -> VolunteerHelpResponse | None:
        return (
            self.db.query(VolunteerHelpResponse)
            .options(
                joinedload(VolunteerHelpResponse.volunteer),
                joinedload(VolunteerHelpResponse.help_request),
                joinedload(VolunteerHelpResponse.report),
            )
            .join(HelpRequest, HelpRequest.id == VolunteerHelpResponse.help_request_id)
            .filter(
                HelpRequest.organization_id == organization_id,
                VolunteerHelpResponse.id == response_id,
            )
            .first()
        )

    def merge_duplicate_org_chat_dialogs(self) -> int:
        dup_groups = (
            self.db.query(
                OrgChatDialog.organization_id,
                OrgChatDialog.participant_user_id,
            )
            .filter(OrgChatDialog.participant_user_id.isnot(None))
            .group_by(OrgChatDialog.organization_id, OrgChatDialog.participant_user_id)
            .having(func.count(OrgChatDialog.id) > 1)
            .all()
        )
        removed = 0
        for org_id, participant_id in dup_groups:
            dialogs = (
                self.db.query(OrgChatDialog)
                .filter(
                    OrgChatDialog.organization_id == org_id,
                    OrgChatDialog.participant_user_id == participant_id,
                )
                .order_by(
                    OrgChatDialog.last_message_at.desc().nullslast(),
                    OrgChatDialog.updated_at.desc(),
                    OrgChatDialog.id.desc(),
                )
                .all()
            )
            if len(dialogs) < 2:
                continue
            keep = dialogs[0]
            for dup in dialogs[1:]:
                self.db.query(OrgChatMessage).filter(OrgChatMessage.dialog_id == dup.id).update(
                    {OrgChatMessage.dialog_id: keep.id},
                    synchronize_session=False,
                )
                keep.unread_count_org = int(keep.unread_count_org or 0) + int(dup.unread_count_org or 0)
                keep.unread_count_volunteer = int(keep.unread_count_volunteer or 0) + int(
                    dup.unread_count_volunteer or 0
                )
                keep.unread_count_user = int(keep.unread_count_user or 0) + int(dup.unread_count_user or 0)
                dup_at = dup.last_message_at
                keep_at = keep.last_message_at
                if dup_at and (keep_at is None or dup_at > keep_at):
                    keep.last_message_preview = dup.last_message_preview
                    keep.last_message_at = dup_at
                if not keep.context_title and dup.context_title:
                    keep.context_title = dup.context_title
                if not keep.context_type and dup.context_type:
                    keep.context_type = dup.context_type
                if keep.context_entity_id is None and dup.context_entity_id is not None:
                    keep.context_entity_id = dup.context_entity_id
                self.db.delete(dup)
                removed += 1
        if removed:
            self.db.flush()
        return removed

    def list_org_dialogs(self, organization_id: int, q: str | None, limit: int, offset: int):
        query = self.db.query(OrgChatDialog).filter(OrgChatDialog.organization_id == organization_id)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(OrgChatDialog.participant_name).like(like),
                    func.lower(func.coalesce(OrgChatDialog.context_title, "")).like(like),
                    func.lower(func.coalesce(OrgChatDialog.last_message_preview, "")).like(like),
                )
            )
        total = query.count()
        rows = (
            query.order_by(
                OrgChatDialog.last_message_at.desc().nullslast(),
                OrgChatDialog.updated_at.desc(),
                OrgChatDialog.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        unread_total = int(
            self.db.query(func.coalesce(func.sum(OrgChatDialog.unread_count_org), 0))
            .filter(OrgChatDialog.organization_id == organization_id)
            .scalar()
            or 0
        )
        return total, unread_total, rows

    def get_org_dialog(self, organization_id: int, dialog_id: int) -> OrgChatDialog | None:
        return (
            self.db.query(OrgChatDialog)
            .filter(
                OrgChatDialog.organization_id == organization_id,
                OrgChatDialog.id == dialog_id,
            )
            .first()
        )

    def list_org_dialog_messages(self, dialog_id: int, limit: int = 150) -> list[OrgChatMessage]:
        return (
            self.db.query(OrgChatMessage)
            .filter(OrgChatMessage.dialog_id == dialog_id)
            .order_by(OrgChatMessage.created_at.asc(), OrgChatMessage.id.asc())
            .limit(limit)
            .all()
        )

    def mark_dialog_messages_read_by_org(self, dialog_id: int) -> None:
        now_expr = func.now()
        self.db.query(OrgChatMessage).filter(
            OrgChatMessage.dialog_id == dialog_id,
            OrgChatMessage.read_by_org_at.is_(None),
            OrgChatMessage.sender_role != UserRole.ORGANIZATION.value,
        ).update({OrgChatMessage.read_by_org_at: now_expr}, synchronize_session=False)
        self.db.query(OrgChatDialog).filter(OrgChatDialog.id == dialog_id).update(
            {OrgChatDialog.unread_count_org: 0}, synchronize_session=False
        )

    def mark_dialog_messages_read_by_volunteer(self, dialog_id: int) -> None:
        now_expr = func.now()
        self.db.query(OrgChatMessage).filter(
            OrgChatMessage.dialog_id == dialog_id,
            OrgChatMessage.read_by_volunteer_at.is_(None),
            OrgChatMessage.sender_role != UserRole.VOLUNTEER.value,
        ).update({OrgChatMessage.read_by_volunteer_at: now_expr}, synchronize_session=False)
        self.db.query(OrgChatDialog).filter(OrgChatDialog.id == dialog_id).update(
            {OrgChatDialog.unread_count_volunteer: 0}, synchronize_session=False
        )

    def find_org_dialog_by_org_and_participant(
        self, organization_id: int, participant_user_id: int
    ) -> OrgChatDialog | None:
        return (
            self.db.query(OrgChatDialog)
            .filter(
                OrgChatDialog.organization_id == organization_id,
                OrgChatDialog.participant_user_id == participant_user_id,
            )
            .order_by(
                OrgChatDialog.last_message_at.desc().nullslast(),
                OrgChatDialog.updated_at.desc(),
                OrgChatDialog.id.desc(),
            )
            .first()
        )

    def participant_is_volunteer(self, user_id: int) -> bool:
        role = self.db.query(User.role).filter(User.id == user_id).scalar()
        if role is None:
            return False
        return role == UserRole.VOLUNTEER or role == UserRole.VOLUNTEER.value

    def participant_is_user(self, user_id: int) -> bool:
        role = self.db.query(User.role).filter(User.id == user_id).scalar()
        if role is None:
            return False
        return role == UserRole.USER or role == UserRole.USER.value

    def get_user_by_id_with_profiles(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .options(
                joinedload(User.volunteer_profile),
                joinedload(User.user_profile),
            )
            .filter(User.id == user_id)
            .first()
        )

    def list_volunteer_dialog_rows(
        self, volunteer_user_id: int, q: str | None, limit: int, offset: int
    ) -> tuple[int, int, list[tuple[OrgChatDialog, Organization]]]:
        query = (
            self.db.query(OrgChatDialog, Organization)
            .join(Organization, Organization.id == OrgChatDialog.organization_id)
            .filter(OrgChatDialog.participant_user_id == volunteer_user_id)
        )
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Organization.name).like(like),
                    func.lower(func.coalesce(OrgChatDialog.context_title, "")).like(like),
                    func.lower(func.coalesce(OrgChatDialog.last_message_preview, "")).like(like),
                )
            )
        total = int(query.count() or 0)
        rows = (
            query.order_by(
                OrgChatDialog.last_message_at.desc().nullslast(),
                OrgChatDialog.updated_at.desc(),
                OrgChatDialog.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        unread_total = int(
            self.db.query(func.coalesce(func.sum(OrgChatDialog.unread_count_volunteer), 0))
            .filter(OrgChatDialog.participant_user_id == volunteer_user_id)
            .scalar()
            or 0
        )
        return total, unread_total, rows

    def get_volunteer_dialog_row(
        self, volunteer_user_id: int, dialog_id: int
    ) -> tuple[OrgChatDialog, Organization] | None:
        row = (
            self.db.query(OrgChatDialog, Organization)
            .join(Organization, Organization.id == OrgChatDialog.organization_id)
            .filter(
                OrgChatDialog.id == dialog_id,
                OrgChatDialog.participant_user_id == volunteer_user_id,
            )
            .first()
        )
        return row if row else None

    def list_user_dialog_rows(
        self, user_id: int, q: str | None, limit: int, offset: int
    ) -> tuple[int, int, list[tuple[OrgChatDialog, Organization]]]:
        query = (
            self.db.query(OrgChatDialog, Organization)
            .join(Organization, Organization.id == OrgChatDialog.organization_id)
            .filter(OrgChatDialog.participant_user_id == user_id)
        )
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Organization.name).like(like),
                    func.lower(func.coalesce(OrgChatDialog.context_title, "")).like(like),
                    func.lower(func.coalesce(OrgChatDialog.last_message_preview, "")).like(like),
                )
            )
        total = int(query.count() or 0)
        rows = (
            query.order_by(
                OrgChatDialog.last_message_at.desc().nullslast(),
                OrgChatDialog.updated_at.desc(),
                OrgChatDialog.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        unread_total = int(
            self.db.query(func.coalesce(func.sum(OrgChatDialog.unread_count_user), 0))
            .filter(OrgChatDialog.participant_user_id == user_id)
            .scalar()
            or 0
        )
        return total, unread_total, rows

    def get_user_dialog_row(
        self, user_id: int, dialog_id: int
    ) -> tuple[OrgChatDialog, Organization] | None:
        row = (
            self.db.query(OrgChatDialog, Organization)
            .join(Organization, Organization.id == OrgChatDialog.organization_id)
            .filter(
                OrgChatDialog.id == dialog_id,
                OrgChatDialog.participant_user_id == user_id,
            )
            .first()
        )
        return row if row else None

    def mark_dialog_messages_read_by_user(self, dialog_id: int) -> None:
        now_expr = func.now()
        self.db.query(OrgChatMessage).filter(
            OrgChatMessage.dialog_id == dialog_id,
            OrgChatMessage.read_by_user_at.is_(None),
            OrgChatMessage.sender_role != UserRole.USER.value,
        ).update({OrgChatMessage.read_by_user_at: now_expr}, synchronize_session=False)
        self.db.query(OrgChatDialog).filter(OrgChatDialog.id == dialog_id).update(
            {OrgChatDialog.unread_count_user: 0}, synchronize_session=False
        )

    def dialog_has_organization_message(self, dialog_id: int) -> bool:
        return (
            self.db.query(OrgChatMessage.id)
            .filter(
                OrgChatMessage.dialog_id == dialog_id,
                OrgChatMessage.sender_role == UserRole.ORGANIZATION.value,
            )
            .first()
            is not None
        )

    def create_org_message(
        self,
        dialog_id: int,
        sender_user_id: int,
        sender_role: str,
        body: str,
        photo_path: str | None = None,
    ) -> OrgChatMessage:
        msg = OrgChatMessage(
            dialog_id=dialog_id,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            body=body,
            photo_path=photo_path,
        )
        self.db.add(msg)
        self.db.flush()
        return msg

    def update_dialog_last_message(self, dialog: OrgChatDialog, preview: str, created_at) -> None:
        p = preview.strip()
        if len(p) > 500:
            p = p[:499].rstrip() + "…"
        dialog.last_message_preview = p or None
        dialog.last_message_at = created_at
        dialog.updated_at = created_at

    def increment_dialog_unread_for_volunteer(self, dialog_id: int) -> None:
        self.db.query(OrgChatDialog).filter(OrgChatDialog.id == dialog_id).update(
            {OrgChatDialog.unread_count_volunteer: OrgChatDialog.unread_count_volunteer + 1},
            synchronize_session=False,
        )

    def increment_dialog_unread_for_org(self, dialog_id: int) -> None:
        self.db.query(OrgChatDialog).filter(OrgChatDialog.id == dialog_id).update(
            {OrgChatDialog.unread_count_org: OrgChatDialog.unread_count_org + 1},
            synchronize_session=False,
        )

    def increment_dialog_unread_for_user(self, dialog_id: int) -> None:
        self.db.query(OrgChatDialog).filter(OrgChatDialog.id == dialog_id).update(
            {OrgChatDialog.unread_count_user: OrgChatDialog.unread_count_user + 1},
            synchronize_session=False,
        )

    def list_org_reports(self, organization_id: int, limit: int, offset: int) -> tuple[int, list[OrganizationReport]]:
        query = self.db.query(OrganizationReport).filter(OrganizationReport.organization_id == organization_id)
        total = int(query.count() or 0)
        rows = (
            query.order_by(OrganizationReport.published_at.desc(), OrganizationReport.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, rows

    def get_org_report(self, organization_id: int, report_id: int) -> OrganizationReport | None:
        return (
            self.db.query(OrganizationReport)
            .filter(OrganizationReport.organization_id == organization_id, OrganizationReport.id == report_id)
            .first()
        )

    def list_org_home_stories(
        self, organization_id: int, limit: int, offset: int
    ) -> tuple[int, list[OrganizationHomeStory]]:
        query = self.db.query(OrganizationHomeStory).filter(OrganizationHomeStory.organization_id == organization_id)
        total = int(query.count() or 0)
        rows = (
            query.order_by(OrganizationHomeStory.adopted_at.desc(), OrganizationHomeStory.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, rows

    def get_org_home_story(self, organization_id: int, story_id: int) -> OrganizationHomeStory | None:
        return (
            self.db.query(OrganizationHomeStory)
            .filter(OrganizationHomeStory.organization_id == organization_id, OrganizationHomeStory.id == story_id)
            .first()
        )

    def list_org_events(self, organization_id: int, limit: int, offset: int) -> tuple[int, list[Event]]:
        query = self.db.query(Event).filter(Event.organization_id == organization_id)
        total = int(query.count() or 0)
        rows = (
            query.order_by(Event.starts_at.desc(), Event.id.desc()).offset(offset).limit(limit).all()
        )
        return total, rows

    def list_org_articles(self, owner_user_id: int, limit: int, offset: int) -> tuple[int, list[KnowledgeArticle]]:
        query = self.db.query(KnowledgeArticle).filter(
            KnowledgeArticle.author_user_id == owner_user_id,
            KnowledgeArticle.owner_role == "organization",
        )
        total = int(query.count() or 0)
        rows = (
            query.order_by(KnowledgeArticle.created_at.desc(), KnowledgeArticle.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, rows

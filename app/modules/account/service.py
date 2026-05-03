import json
from datetime import datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.adoption_application import AdoptionApplicationStatus, AnimalAdoptionApplication
from app.models.animal import AnimalStatus
from app.models.profile import UserProfile, VolunteerProfile
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.models.volunteer_help_response import VolunteerHelpResponse, VolunteerHelpResponseStatus
from app.models.volunteer_help_response_report import VolunteerHelpResponseReport
from app.models.user import User, UserRole
from app.modules.account.repository import AccountRepository
from app.modules.account import schemas as s
from app.modules.account.storage import save_profile_avatar
from app.modules.animals.jsonutil import parse_json_list
from app.modules.animals.tags import species_label_ru
from app.modules.organizations.repository import OrganizationRepository
from app.modules.urgent.schemas import HELP_TYPE_OPTIONS
from app.modules.volunteers.constants import (
    ALLOWED_HELP_FORMATS,
    ALLOWED_TRAVEL_AREA_MODES,
    ANIMAL_TYPE_FILTER_OPTIONS,
    COMPETENCY_OPTIONS,
    EXPERIENCE_LEVEL_OPTIONS,
)
from app.modules.volunteers.schemas import VolunteerWeeklySlot

_ALLOWED_ANIMAL_TYPE_IDS = {x["id"] for x in ANIMAL_TYPE_FILTER_OPTIONS if x["id"] != "all"}
_ALLOWED_COMPETENCY_SLUGS = {x["id"] for x in COMPETENCY_OPTIONS}
_ALLOWED_EXPERIENCE = {x["id"] for x in EXPERIENCE_LEVEL_OPTIONS}

_HELP_TYPE_LABELS: dict[str, str] = {x["id"]: x["label"] for x in HELP_TYPE_OPTIONS}


def _help_request_deadline_label(deadline_at: datetime | None, deadline_note: str | None) -> str | None:
    if deadline_note is not None and deadline_note.strip():
        return deadline_note.strip()
    if deadline_at is None:
        return None
    now = datetime.utcnow()
    if deadline_at.date() == now.date():
        return f"Сегодня, {deadline_at.strftime('%H:%M')}"
    return deadline_at.strftime("%d.%m, %H:%M")


def _description_snippet(text: str | None, max_len: int = 220) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _age_label_ru(months: int) -> str:
    if months is None or months <= 0:
        return "Возраст не указан"
    years = months // 12
    mo = months % 12
    if years <= 0:
        if mo == 1:
            return "1 месяц"
        if 2 <= mo <= 4:
            return f"{mo} месяца"
        return f"{mo} месяцев"
    if years == 1:
        y = "1 год"
    elif 2 <= years <= 4:
        y = f"{years} года"
    else:
        y = f"{years} лет"
    if mo == 0:
        return y
    return f"{y} {mo} мес."


def _primary_photo_url(animal) -> str | None:
    if not animal or not animal.photos:
        return None
    primary = next((p for p in animal.photos if p.is_primary), None) or animal.photos[0]
    return f"{settings.media_url_prefix}/{primary.file_path}"


class AccountService:
    def __init__(self, repo: AccountRepository):
        self.repo = repo

    def _media_url(self, path: str | None) -> str | None:
        if not path:
            return None
        return f"{settings.media_url_prefix}/{path}"

    def _competency_pairs(self, profile: VolunteerProfile) -> tuple[list[str], list[str]]:
        assigns = list(profile.competency_assignments or [])
        pairs: list[tuple[int, str, str]] = []
        for a in assigns:
            it = a.competency_item
            if it is None:
                continue
            pairs.append((int(it.sort_order or 0), it.slug, it.label))
        pairs.sort(key=lambda x: (x[0], x[1]))
        return [p[1] for p in pairs], [p[2] for p in pairs]

    @staticmethod
    def _weekly_slots_for_me(vp: VolunteerProfile) -> list[VolunteerWeeklySlot]:
        raw = getattr(vp, "weekly_availability_json", None)
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        out: list[VolunteerWeeklySlot] = []
        for chunk in data:
            try:
                out.append(VolunteerWeeklySlot.model_validate(chunk))
            except Exception:
                continue
        return out

    def get_profile(self, user: User) -> s.MeProfileResponse:
        u = self.repo.get_user_me(user.id)
        if u is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        brief = s.MeUserBrief.model_validate(u)
        user_prof: s.MeUserProfileOut | None = None
        vol_prof: s.MeVolunteerProfileOut | None = None

        if u.role == UserRole.USER and u.user_profile is not None:
            up = u.user_profile
            user_prof = s.MeUserProfileOut(avatar_url=self._media_url(up.avatar_path))
        elif u.role == UserRole.USER:
            user_prof = s.MeUserProfileOut(avatar_url=None)

        if u.role == UserRole.VOLUNTEER and u.volunteer_profile is not None:
            vp = u.volunteer_profile
            slugs, labels = self._competency_pairs(vp)
            animal_ids = parse_json_list(vp.animal_types_json)
            vol_prof = s.MeVolunteerProfileOut(
                about_me=vp.about_me,
                availability=vp.availability,
                location_city=vp.location_city,
                location_district=getattr(vp, "location_district", None),
                travel_radius_km=vp.travel_radius_km,
                help_format=getattr(vp, "help_format", None),
                has_veterinary_education=bool(getattr(vp, "has_veterinary_education", False)),
                weekly_availability=self._weekly_slots_for_me(vp),
                accepts_night_urgency=bool(getattr(vp, "accepts_night_urgency", False)),
                travel_area_mode=getattr(vp, "travel_area_mode", None),
                animal_types=animal_ids,
                experience_level=vp.experience_level,
                competency_slugs=slugs,
                competency_labels=labels,
                is_available=bool(vp.is_available),
                has_own_transport=bool(vp.has_own_transport),
                can_travel_other_area=bool(vp.can_travel_other_area),
                latitude=vp.latitude,
                longitude=vp.longitude,
                avatar_url=self._media_url(vp.avatar_path),
            )

        return s.MeProfileResponse(user=brief, user_profile=user_prof, volunteer_profile=vol_prof)

    def patch_profile(self, user: User, payload: s.MeProfilePatchRequest) -> s.MeProfileResponse:
        u = self.repo.get_user_me(user.id)
        if u is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        changed = False

        if u.role == UserRole.USER and payload.user_fields is not None:
            uf = payload.user_fields
            if uf.full_name is not None:
                u.full_name = uf.full_name.strip() or None
                changed = True

        elif u.role == UserRole.VOLUNTEER and payload.volunteer is not None:
            vf = payload.volunteer
            if vf.full_name is not None:
                u.full_name = vf.full_name.strip() or None
                changed = True
            vp = u.volunteer_profile
            if vp is None:
                vp = VolunteerProfile(user_id=u.id)
                self.repo.db.add(vp)
                self.repo.db.flush()
                u.volunteer_profile = vp
            if vf.about_me is not None:
                vp.about_me = vf.about_me
                changed = True
            if vf.availability is not None:
                vp.availability = vf.availability
                changed = True
            if vf.location_city is not None:
                vp.location_city = vf.location_city
                changed = True
            if vf.location_district is not None:
                vp.location_district = vf.location_district.strip() or None
                changed = True
            if vf.travel_radius_km is not None:
                vp.travel_radius_km = vf.travel_radius_km
                changed = True
            if vf.help_format is not None:
                hf = vf.help_format.strip()
                if not hf:
                    vp.help_format = None
                    changed = True
                elif hf not in ALLOWED_HELP_FORMATS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Неизвестный формат помощи",
                    )
                else:
                    vp.help_format = hf
                    changed = True
            if vf.has_veterinary_education is not None:
                vp.has_veterinary_education = bool(vf.has_veterinary_education)
                changed = True
            if vf.weekly_availability is not None:
                dumped = [slot.model_dump(mode="json") for slot in vf.weekly_availability]
                vp.weekly_availability_json = json.dumps(dumped, ensure_ascii=False)
                changed = True
            if vf.accepts_night_urgency is not None:
                vp.accepts_night_urgency = bool(vf.accepts_night_urgency)
                changed = True
            if vf.travel_area_mode is not None:
                mode = vf.travel_area_mode.strip()
                if not mode:
                    vp.travel_area_mode = None
                    changed = True
                elif mode not in ALLOWED_TRAVEL_AREA_MODES:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Неизвестный режим выезда",
                    )
                else:
                    vp.travel_area_mode = mode
                    changed = True
            if vf.animal_types is not None:
                bad = [x for x in vf.animal_types if x not in _ALLOWED_ANIMAL_TYPE_IDS]
                if bad:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Неизвестные категории животных: {', '.join(bad)}",
                    )
                vp.animal_types_json = json.dumps(vf.animal_types, ensure_ascii=False)
                changed = True
            if vf.competency_slugs is not None:
                unk = sorted(set(vf.competency_slugs) - _ALLOWED_COMPETENCY_SLUGS)
                if unk:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Неизвестные компетенции: {', '.join(unk)}",
                    )
                items = (
                    self.repo.db.query(VolunteerCompetencyItem)
                    .filter(
                        VolunteerCompetencyItem.slug.in_(vf.competency_slugs),
                        VolunteerCompetencyItem.is_active.is_(True),
                    )
                    .all()
                )
                slug_to_item = {it.slug: it for it in items}
                ordered = [slug_to_item[s] for s in vf.competency_slugs if s in slug_to_item]
                if len(ordered) != len(vf.competency_slugs):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Одна или несколько компетенций не найдены",
                    )
                self.repo.db.query(VolunteerCompetencyAssignment).filter(
                    VolunteerCompetencyAssignment.volunteer_profile_id == vp.id
                ).delete(synchronize_session=False)
                for it in ordered:
                    self.repo.db.add(
                        VolunteerCompetencyAssignment(volunteer_profile_id=vp.id, competency_item_id=it.id)
                    )
                changed = True
            if vf.experience_level is not None:
                if vf.experience_level not in _ALLOWED_EXPERIENCE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Неизвестный уровень опыта",
                    )
                vp.experience_level = vf.experience_level
                changed = True
            if vf.is_available is not None:
                vp.is_available = vf.is_available
                changed = True
            if vf.has_own_transport is not None:
                vp.has_own_transport = vf.has_own_transport
                changed = True
            if vf.can_travel_other_area is not None:
                vp.can_travel_other_area = vf.can_travel_other_area
                changed = True
            if vf.latitude is not None:
                vp.latitude = vf.latitude
                changed = True
            if vf.longitude is not None:
                vp.longitude = vf.longitude
                changed = True

        elif u.role == UserRole.ORGANIZATION and payload.organization_contact is not None:
            oc = payload.organization_contact
            if oc.full_name is not None:
                u.full_name = oc.full_name.strip() or None
                changed = True

        if not changed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")

        self.repo.db.commit()
        self.repo.db.refresh(u)
        return self.get_profile(u)

    def upload_avatar(self, user: User, file: UploadFile) -> s.AvatarUploadResponse:
        u = self.repo.get_user_me(user.id)
        if u is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if u.role == UserRole.ORGANIZATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Аватар профиля для организации не поддерживается",
            )

        try:
            if u.role == UserRole.VOLUNTEER:
                path = save_profile_avatar(settings.media_dir, u.id, "volunteer", file)
                vp = u.volunteer_profile
                if vp is None:
                    vp = VolunteerProfile(user_id=u.id)
                    self.repo.db.add(vp)
                    self.repo.db.flush()
                vp.avatar_path = path
            else:
                path = save_profile_avatar(settings.media_dir, u.id, "user", file)
                up = self.repo.get_or_create_user_profile(u.id)
                up.avatar_path = path
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        self.repo.db.commit()
        return s.AvatarUploadResponse(avatar_url=self._media_url(path) or "")

    def _assert_can_apply_adoption(self, user: User, animal_id: int):
        animal = self.repo.get_animal(animal_id)
        if animal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Животное не найдено")
        if animal.status in (AnimalStatus.ADOPTED.value, AnimalStatus.ARCHIVED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя подать анкету на это животное",
            )
        if user.role == UserRole.ORGANIZATION:
            org_repo = OrganizationRepository(self.repo.db)
            org = org_repo.get_owned_by_user(user.id)
            if org is not None and animal.organization_id == org.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Нельзя подать анкету на животное своей организации",
                )

    def create_application(self, user: User, payload: s.AdoptionApplicationCreate) -> s.AdoptionApplicationDetail:
        if user.role not in (UserRole.USER, UserRole.VOLUNTEER):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно пользователям и волонтёрам")

        self._assert_can_apply_adoption(user, payload.animal_id)

        existing = self.repo.get_application_by_user_animal(user.id, payload.animal_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Анкета на это животное уже есть",
            )

        row = AnimalAdoptionApplication(
            user_id=user.id,
            animal_id=payload.animal_id,
            status=AdoptionApplicationStatus.PENDING_REVIEW.value,
            message=payload.message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.repo.db.add(row)
        try:
            self.repo.db.commit()
            self.repo.db.refresh(row)
        except IntegrityError as exc:
            self.repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Анкета на это животное уже есть",
            ) from exc

        got = self.repo.get_application(row.id, user.id)
        assert got is not None
        return self._application_detail(got)

    def list_applications(
        self, user: User, q: str | None, limit: int, offset: int
    ) -> s.AdoptionApplicationListResponse:
        if user.role not in (UserRole.USER, UserRole.VOLUNTEER):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно пользователям и волонтёрам")

        total = self.repo.count_applications(user.id, q)
        rows = self.repo.list_applications(user.id, q, limit, offset)
        items = [self._application_item(r) for r in rows]
        return s.AdoptionApplicationListResponse(total=total, items=items)

    def _application_item(self, row: AnimalAdoptionApplication) -> s.AdoptionApplicationListItem:
        a = row.animal
        org_name = a.organization.name if a and a.organization else None
        return s.AdoptionApplicationListItem(
            id=row.id,
            status=row.status,
            status_label=s.APPLICATION_STATUS_LABELS.get(row.status, row.status),
            animal_id=a.id if a else 0,
            animal_name=a.name if a else "?",
            species_label=species_label_ru(a.species if a else "cat", a.sex if a else "unknown"),
            breed=a.breed if a else None,
            age_label=_age_label_ru(int(a.age_months or 0) if a else 0),
            primary_photo_url=_primary_photo_url(a),
            organization_name=org_name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _application_detail(self, row: AnimalAdoptionApplication) -> s.AdoptionApplicationDetail:
        base = self._application_item(row)
        return s.AdoptionApplicationDetail(**base.model_dump(), message=row.message)

    def get_application(self, user: User, application_id: int) -> s.AdoptionApplicationDetail:
        if user.role not in (UserRole.USER, UserRole.VOLUNTEER):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступно пользователям и волонтёрам")

        row = self.repo.get_application(application_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        return self._application_detail(row)

    def update_application(
        self, user: User, application_id: int, payload: s.AdoptionApplicationUpdate
    ) -> s.AdoptionApplicationDetail:
        row = self.repo.get_application(application_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        if row.status != AdoptionApplicationStatus.PENDING_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Редактировать можно только анкету на рассмотрении",
            )
        if "message" not in payload.model_fields_set:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
        row.message = payload.message
        row.updated_at = datetime.utcnow()
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._application_detail(row)

    def delete_application(self, user: User, application_id: int) -> None:
        row = self.repo.get_application(application_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        self.repo.db.delete(row)
        self.repo.db.commit()

    def _help_request_accepting_volunteers(self, req) -> bool:
        return bool(
            req
            and not req.is_archived
            and req.is_published
            and req.volunteer_needed
            and req.status in ("open", "in_progress")
        )

    def create_volunteer_response(
        self, user: User, payload: s.VolunteerHelpResponseCreate
    ) -> s.VolunteerResponseDetail:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")

        req = self.repo.get_help_request(payload.help_request_id)
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
        if not self._help_request_accepting_volunteers(req):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="На эту заявку нельзя откликнуться",
            )

        row = VolunteerHelpResponse(
            volunteer_user_id=user.id,
            help_request_id=payload.help_request_id,
            status=VolunteerHelpResponseStatus.PENDING.value,
            message=payload.message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.repo.db.add(row)
        try:
            self.repo.db.commit()
            self.repo.db.refresh(row)
        except IntegrityError as exc:
            self.repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Отклик на эту заявку уже отправлен",
            ) from exc

        got = self.repo.get_volunteer_response(row.id, user.id)
        assert got is not None
        return self._response_detail(got)

    def _response_card(self, row: VolunteerHelpResponse) -> s.VolunteerResponseCard:
        hr = row.help_request
        rep = row.report
        st = row.status
        org = hr.organization if hr else None
        report_awaiting = bool(
            st == VolunteerHelpResponseStatus.ACCEPTED.value
            and rep is not None
            and rep.org_accepted_at is None
            and rep.org_rejection_reason is None
        )
        archive_like = st in (
            VolunteerHelpResponseStatus.REJECTED.value,
            VolunteerHelpResponseStatus.WITHDRAWN.value,
        )
        can_chat = not archive_like
        can_cancel = st == VolunteerHelpResponseStatus.PENDING.value
        can_send_report = False
        if st == VolunteerHelpResponseStatus.ACCEPTED.value:
            if rep is None:
                can_send_report = True
            elif rep.org_accepted_at is not None:
                can_send_report = False
            elif rep.org_rejection_reason:
                can_send_report = True
            else:
                can_send_report = False
        can_view_report = st == VolunteerHelpResponseStatus.COMPLETED.value

        return s.VolunteerResponseCard(
            id=row.id,
            status=st,
            status_label=s.VOLUNTEER_RESPONSE_STATUS_LABELS.get(st, st),
            report_awaiting_org_review=report_awaiting,
            help_request_id=hr.id if hr else 0,
            title=hr.title if hr else "?",
            description_snippet=_description_snippet(hr.description if hr else ""),
            organization_id=org.id if org else None,
            organization_name=org.name if org else None,
            city=hr.city if hr else None,
            help_type=hr.help_type if hr else "?",
            help_type_label=_HELP_TYPE_LABELS.get(hr.help_type if hr else "", hr.help_type if hr else None),
            is_urgent=bool(hr.is_urgent) if hr else False,
            volunteer_needed=bool(hr.volunteer_needed) if hr else False,
            deadline_at=hr.deadline_at if hr else None,
            deadline_label=_help_request_deadline_label(
                hr.deadline_at if hr else None,
                hr.deadline_note if hr else None,
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
            can_chat=can_chat,
            can_cancel_response=can_cancel,
            can_send_report=can_send_report,
            can_view_report=can_view_report,
            chat_thread_id=None,
        )

    def _response_detail(self, row: VolunteerHelpResponse) -> s.VolunteerResponseDetail:
        hr = row.help_request
        card = self._response_card(row)
        return s.VolunteerResponseDetail(
            **card.model_dump(),
            message=row.message,
            help_request_description=(hr.description if hr else "") or "",
        )

    def list_volunteer_responses(
        self, user: User, q: str | None, tab: str, limit: int, offset: int
    ) -> s.VolunteerHelpResponseListResponse:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")

        total = self.repo.count_volunteer_responses(user.id, q, tab)
        rows = self.repo.list_volunteer_responses(user.id, q, tab, limit, offset)
        items = [self._response_card(r) for r in rows]
        return s.VolunteerHelpResponseListResponse(total=total, items=items)

    def get_volunteer_response(self, user: User, response_id: int) -> s.VolunteerResponseDetail:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")

        row = self.repo.get_volunteer_response(response_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        return self._response_detail(row)

    def update_volunteer_response(
        self, user: User, response_id: int, payload: s.VolunteerHelpResponseUpdate
    ) -> s.VolunteerResponseDetail:
        row = self.repo.get_volunteer_response(response_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")

        if row.status == VolunteerHelpResponseStatus.WITHDRAWN.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отклик уже отозван")

        if row.status != VolunteerHelpResponseStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Сообщение можно менять только у отклика на рассмотрении",
            )

        if "message" not in payload.model_fields_set:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
        row.message = payload.message
        row.updated_at = datetime.utcnow()
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._response_detail(row)

    def withdraw_volunteer_response(self, user: User, response_id: int) -> s.VolunteerResponseDetail:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
        row = self.repo.get_volunteer_response(response_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        if row.status != VolunteerHelpResponseStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Отменить можно только отклик на рассмотрении",
            )
        row.status = VolunteerHelpResponseStatus.WITHDRAWN.value
        row.updated_at = datetime.utcnow()
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._response_detail(row)

    def submit_volunteer_response_report(
        self, user: User, response_id: int, payload: s.VolunteerReportCreate
    ) -> s.VolunteerResponseDetail:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
        row = self.repo.get_volunteer_response(response_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        if row.status != VolunteerHelpResponseStatus.ACCEPTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Отчёт можно отправить только по отклику в работе",
            )
        rep = row.report
        if rep is not None and rep.org_accepted_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отчёт уже принят организацией")
        now = datetime.utcnow()
        if rep is None:
            self.repo.db.add(
                VolunteerHelpResponseReport(
                    volunteer_help_response_id=row.id,
                    body=payload.content,
                    submitted_at=now,
                )
            )
        else:
            rep.body = payload.content
            rep.submitted_at = now
            if rep.org_rejection_reason is not None:
                rep.org_rejection_reason = None
        row.updated_at = now
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._response_detail(row)

    def get_volunteer_response_report(self, user: User, response_id: int) -> s.VolunteerReportOut:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
        row = self.repo.get_volunteer_response(response_id, user.id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        if row.status != VolunteerHelpResponseStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Просмотр отчёта доступен для завершённых откликов",
            )
        rep = row.report
        if rep is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отчёт не найден")
        return s.VolunteerReportOut(
            id=rep.id,
            volunteer_help_response_id=rep.volunteer_help_response_id,
            content=rep.body,
            submitted_at=rep.submitted_at,
            org_accepted_at=rep.org_accepted_at,
            org_rejection_reason=rep.org_rejection_reason,
        )

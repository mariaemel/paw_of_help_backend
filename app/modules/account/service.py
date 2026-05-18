import json
from datetime import datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.adoption_application import AdoptionApplicationStatus, AnimalAdoptionApplication
from app.models.animal import Animal, AnimalStatus
from app.models.help_request import HelpRequest
from app.models.org_chat import OrgChatDialog
from app.models.organization_home_story import OrganizationHomeStory
from app.models.organization_report import OrganizationReport
from app.models.profile import UserProfile, VolunteerProfile
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.models.volunteer_help_response import VolunteerHelpResponse, VolunteerHelpResponseStatus
from app.models.volunteer_help_response_report import VolunteerHelpResponseReport
from app.models.user import User, UserRole
from app.modules.account.repository import AccountRepository
from app.modules.account import schemas as s
from app.modules.account.storage import (
    save_org_asset,
    save_org_chat_message_photo,
    save_profile_avatar,
)
from app.modules.animals.jsonutil import parse_json_list
from app.modules.animals.tags import species_label_ru
from app.modules.organizations.service import OrganizationService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.urgent.schemas import HELP_TYPE_OPTIONS
from app.modules.account.adoption_form import (
    AdoptionApplicationFormBody,
    adoption_form_from_row,
    adoption_form_to_dict,
    apply_adoption_form_patch,
)
from app.modules.help_requests.requisites import effective_payment_bank_account, uses_organization_payment_details
from app.modules.urgent.schemas import UrgentRequestCreate, UrgentRequestDetail, UrgentRequestUpdate
from app.modules.urgent.repository import UrgentRepository
from app.modules.urgent.service import UrgentService
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


def _load_social_links(raw: str | None) -> list[s.OrgSocialLinkIn]:
    if not raw:
        return []
    try:
        arr = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(arr, list):
        return []
    out: list[s.OrgSocialLinkIn] = []
    for row in arr[:3]:
        if not isinstance(row, dict):
            continue
        platform = str(row.get("platform") or row.get("label") or "").strip().lower()
        if platform in ("вконтакте", "vk.com", "вк"):
            platform = "vk"
        elif platform in ("телеграм", "telegram"):
            platform = "telegram"
        elif platform in ("whatsapp", "ватсап", "вацап"):
            platform = "whatsapp"
        url = str(row.get("url") or "").strip()
        if platform not in {"vk", "telegram", "whatsapp"} or not url:
            continue
        out.append(s.OrgSocialLinkIn(platform=platform, url=url))
    return out


def _parse_gallery(raw: str | None) -> list[dict[str, str | None]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str | None]] = []
    for row in data[:5]:
        if isinstance(row, str) and row.strip():
            out.append({"path": row.strip(), "description": None})
            continue
        if isinstance(row, dict):
            p = str(row.get("path") or "").strip()
            if not p:
                continue
            d = row.get("description")
            out.append({"path": p, "description": (str(d).strip() if d is not None else None)})
    return out


class AccountService:
    def __init__(self, repo: AccountRepository):
        self.repo = repo

    def _media_url(self, path: str | None) -> str | None:
        if not path:
            return None
        return f"{settings.media_url_prefix}/{path}"

    def _organization_for_user(self, user: User):
        if user.role != UserRole.ORGANIZATION:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для организаций")
        org = OrganizationRepository(self.repo.db).get_owned_by_user(user.id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Организация для пользователя не найдена",
            )
        return org

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

        form = AdoptionApplicationFormBody.model_validate(
            payload.model_dump(exclude={"animal_id"}, exclude_none=True)
        )
        row = AnimalAdoptionApplication(
            user_id=user.id,
            animal_id=payload.animal_id,
            status=AdoptionApplicationStatus.PENDING_REVIEW.value,
            message=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **adoption_form_to_dict(form),
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
        org_id = a.organization_id if a else None
        thread_id = (
            self._chat_thread_id_for_participant(org_id, row.user_id) if org_id is not None else None
        )
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
            chat_thread_id=thread_id,
        )

    def _application_detail(self, row: AnimalAdoptionApplication) -> s.AdoptionApplicationDetail:
        base = self._application_item(row)
        return s.AdoptionApplicationDetail(**base.model_dump(), **adoption_form_from_row(row), message=row.message)

    def _org_incoming_adoption_item(
        self, row: AnimalAdoptionApplication, organization_id: int | None = None
    ) -> s.OrgIncomingAdoptionItem:
        org_id = organization_id
        if org_id is None and row.animal is not None:
            org_id = row.animal.organization_id
        thread_id = self._chat_thread_id_for_participant(org_id, row.user_id) if org_id else None
        return s.OrgIncomingAdoptionItem(
            id=row.id,
            applicant_user_id=row.user_id,
            animal_id=row.animal_id,
            animal_name=row.animal.name if row.animal else "?",
            created_at=row.created_at,
            status=row.status,
            status_label=s.APPLICATION_STATUS_LABELS.get(row.status, row.status),
            message=row.message,
            chat_thread_id=thread_id,
            **adoption_form_from_row(row),
        )

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
        if not apply_adoption_form_patch(row, payload):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
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

        thread_id: str | None = None
        if can_chat and hr and hr.organization_id:
            dialog = self.repo.find_org_dialog_by_org_and_participant(
                hr.organization_id, row.volunteer_user_id
            )
            if dialog is not None:
                thread_id = str(dialog.id)

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
            chat_thread_id=thread_id,
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

    def get_org_cabinet_profile(self, user: User) -> s.OrgCabinetProfileResponse:
        org = self._organization_for_user(user)
        gallery_entries = _parse_gallery(getattr(org, "gallery_json", None))
        gallery_items: list[s.OrgGalleryImageItem] = []
        for item in gallery_entries:
            p = item.get("path")
            if not p:
                continue
            u = self._media_url(str(p))
            if not u:
                continue
            gallery_items.append(
                s.OrgGalleryImageItem(
                    url=u,
                    description=item.get("description"),
                )
            )
        return s.OrgCabinetProfileResponse(
            profile=s.OrgCabinetProfileOut(
                name=org.name,
                specialization=org.tagline or org.specialization,
                description=org.description,
                city=org.city,
                logo_url=self._media_url(org.logo_path),
                cover_url=self._media_url(org.cover_path),
            ),
            contacts=s.OrgCabinetContactsOut(
                phone=org.phone,
                email=org.email,
                social_links=_load_social_links(org.social_links_json),
            ),
            about=s.OrgCabinetAboutOut(
                history=org.about_html,
                gallery=gallery_items,
                inn=org.inn,
                ogrn=org.ogrn,
                bank_account=org.bank_account,
            ),
            instructions=s.OrgCabinetInstructionsOut(
                adoption_howto=org.adoption_howto,
                admission_rules=org.admission_rules,
            ),
        )

    def patch_org_cabinet_profile(
        self, user: User, payload: s.OrgCabinetProfilePatchRequest
    ) -> s.OrgCabinetProfileResponse:
        org = self._organization_for_user(user)
        changed = False
        if payload.profile is not None:
            pf = payload.profile
            if pf.name is not None:
                org.name = pf.name.strip() or org.name
                changed = True
            if pf.specialization is not None:
                org.tagline = pf.specialization.strip() or None
                changed = True
            if pf.description is not None:
                org.description = pf.description.strip() or None
                changed = True
            if pf.city is not None:
                org.city = pf.city.strip() or None
                changed = True
        if payload.contacts is not None:
            ct = payload.contacts
            if ct.phone is not None:
                org.phone = ct.phone.strip() or None
                changed = True
            if ct.email is not None:
                org.email = str(ct.email).strip() or None
                changed = True
            if ct.social_links is not None:
                links = [x.model_dump() for x in ct.social_links[:3]]
                org.social_links_json = json.dumps(links, ensure_ascii=False)
                changed = True
        if payload.about is not None:
            ab = payload.about
            if ab.history is not None:
                org.about_html = ab.history.strip() or None
                changed = True
            if ab.gallery is not None:
                existing = _parse_gallery(org.gallery_json)
                by_path: dict[str, dict[str, str | None]] = {str(x["path"]): x for x in existing if x.get("path")}
                for gi in ab.gallery:
                    rel = gi.url.replace(settings.media_url_prefix + "/", "", 1).strip()
                    if rel in by_path:
                        by_path[rel]["description"] = gi.description.strip() if gi.description else None
                merged: list[dict[str, str | None]] = []
                for x in existing[:5]:
                    p = x.get("path")
                    if not p:
                        continue
                    merged.append({"path": str(p), "description": by_path[str(p)].get("description")})
                org.gallery_json = json.dumps(merged, ensure_ascii=False)
                changed = True
            if ab.inn is not None:
                org.inn = ab.inn.strip() or None
                changed = True
            if ab.ogrn is not None:
                org.ogrn = ab.ogrn.strip() or None
                changed = True
            if ab.bank_account is not None:
                org.bank_account = ab.bank_account.strip() or None
                changed = True
        if payload.instructions is not None:
            ins = payload.instructions
            if ins.adoption_howto is not None:
                org.adoption_howto = ins.adoption_howto.strip() or None
                changed = True
            if ins.admission_rules is not None:
                org.admission_rules = ins.admission_rules.strip() or None
                changed = True
        if not changed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
        self.repo.db.commit()
        return self.get_org_cabinet_profile(user)

    def upload_org_logo(self, user: User, file: UploadFile) -> s.OrgAssetUploadResponse:
        org = self._organization_for_user(user)
        try:
            path = save_org_asset(settings.media_dir, org.id, "logo", file, max_size_bytes=2 * 1024 * 1024)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        org.logo_path = path
        self.repo.db.commit()
        return s.OrgAssetUploadResponse(url=self._media_url(path) or "")

    def upload_org_cover(self, user: User, file: UploadFile) -> s.OrgAssetUploadResponse:
        org = self._organization_for_user(user)
        try:
            path = save_org_asset(settings.media_dir, org.id, "cover", file, max_size_bytes=5 * 1024 * 1024)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        org.cover_path = path
        self.repo.db.commit()
        return s.OrgAssetUploadResponse(url=self._media_url(path) or "")

    def upload_org_gallery_image(
        self,
        user: User,
        file: UploadFile,
        description: str | None = None,
    ) -> s.OrgAssetUploadResponse:
        org = self._organization_for_user(user)
        existing = _parse_gallery(org.gallery_json)
        if len(existing) >= 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Можно загрузить не более 5 изображений")
        try:
            path = save_org_asset(settings.media_dir, org.id, "gallery", file, max_size_bytes=5 * 1024 * 1024)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        existing.append(
            {
                "path": path,
                "description": description.strip() if description and description.strip() else None,
            }
        )
        org.gallery_json = json.dumps(existing[:5], ensure_ascii=False)
        self.repo.db.commit()
        gallery_items = [
            s.OrgGalleryImageItem(
                url=self._media_url(str(row["path"])) or "",
                description=row.get("description"),
            )
            for row in existing[:5]
            if row.get("path")
        ]
        return s.OrgAssetUploadResponse(
            url=self._media_url(path) or "",
            gallery=gallery_items,
        )

    def get_org_public_preview(self, user: User):
        org = self._organization_for_user(user)
        return OrganizationService(OrganizationRepository(self.repo.db)).get_public_page(org.id)

    def _org_owned_animal_item(self, a: Animal) -> s.OrgOwnedAnimalItem:
        return s.OrgOwnedAnimalItem(
            id=a.id,
            name=a.name,
            species=a.species,
            age_months=int(a.age_months or 0),
            status=a.status,
            is_urgent=bool(a.is_urgent),
            primary_photo_url=_primary_photo_url(a),
            created_at=a.created_at,
        )

    def list_org_animals(self, user: User, q: str | None, limit: int, offset: int) -> s.OrgOwnedAnimalListResponse:
        org = self._organization_for_user(user)
        total = self.repo.count_org_animals(org.id, q)
        rows = self.repo.list_org_animals(org.id, q, limit, offset)
        return s.OrgOwnedAnimalListResponse(total=total, items=[self._org_owned_animal_item(a) for a in rows])

    def create_org_animal(self, user: User, payload: s.OrgOwnedAnimalCreate) -> s.OrgOwnedAnimalItem:
        org = self._organization_for_user(user)
        a = Animal(
            organization_id=org.id,
            name=payload.name,
            species=payload.species,
            sex=payload.sex,
            age_months=payload.age_months,
            breed=payload.breed,
            status=payload.status,
            full_description=payload.full_description,
            location_city=payload.location_city or org.city,
            is_urgent=payload.is_urgent,
        )
        self.repo.db.add(a)
        self.repo.db.commit()
        self.repo.db.refresh(a)
        return self._org_owned_animal_item(a)

    def update_org_animal(self, user: User, animal_id: int, payload: s.OrgOwnedAnimalUpdate) -> s.OrgOwnedAnimalItem:
        org = self._organization_for_user(user)
        a = self.repo.get_org_animal(org.id, animal_id)
        if a is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
        changed = False
        for field in (
            "name",
            "status",
            "age_months",
            "breed",
            "full_description",
            "location_city",
            "is_urgent",
        ):
            if getattr(payload, field) is not None:
                setattr(a, field, getattr(payload, field))
                changed = True
        if not changed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
        self.repo.db.commit()
        self.repo.db.refresh(a)
        return self._org_owned_animal_item(a)

    def archive_org_animal(self, user: User, animal_id: int) -> s.OrgOwnedAnimalItem:
        org = self._organization_for_user(user)
        a = self.repo.get_org_animal(org.id, animal_id)
        if a is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Питомец не найден")
        a.status = "archived"
        self.repo.db.commit()
        self.repo.db.refresh(a)
        return self._org_owned_animal_item(a)

    @staticmethod
    def _help_type_group(help_type: str) -> str:
        return "fundraising" if help_type in ("financial", "food", "medical") else "volunteer_task"

    def _org_owned_help_item(self, row: HelpRequest) -> s.OrgOwnedHelpRequestItem:
        return s.OrgOwnedHelpRequestItem(
            id=row.id,
            title=row.title,
            description=row.description or "",
            type_group=self._help_type_group(row.help_type),
            help_type=row.help_type,
            animal_id=row.animal_id,
            animal_name=row.animal.name if row.animal else None,
            animal_photo_url=_primary_photo_url(row.animal),
            status=row.status,
            is_urgent=bool(row.is_urgent),
            target_amount=row.target_amount,
            deadline_at=row.deadline_at,
            deadline_note=row.deadline_note,
            payment_bank_account=effective_payment_bank_account(row),
            uses_organization_payment_details=uses_organization_payment_details(row),
            created_at=row.created_at,
        )

    def list_org_help_requests(
        self,
        user: User,
        q: str | None,
        tab: str | None,
        limit: int,
        offset: int,
    ) -> s.OrgOwnedHelpRequestListResponse:
        org = self._organization_for_user(user)
        total = self.repo.count_org_help_requests(org.id, q, tab)
        rows = self.repo.list_org_help_requests(org.id, q, tab, limit, offset)
        return s.OrgOwnedHelpRequestListResponse(total=total, items=[self._org_owned_help_item(r) for r in rows])

    def create_org_help_request(self, user: User, payload: UrgentRequestCreate) -> UrgentRequestDetail:
        return UrgentService(UrgentRepository(self.repo.db)).create_request(user, payload)

    def update_org_help_request(
        self, user: User, request_id: int, payload: UrgentRequestUpdate
    ) -> UrgentRequestDetail:
        return UrgentService(UrgentRepository(self.repo.db)).update_request(request_id, user, payload)

    def close_org_help_request(self, user: User, request_id: int) -> UrgentRequestDetail:
        return UrgentService(UrgentRepository(self.repo.db)).close_request(request_id, user)

    def list_org_incoming_adoptions(
        self, user: User, q: str | None, status_value: str | None, limit: int, offset: int
    ) -> s.OrgIncomingAdoptionListResponse:
        org = self._organization_for_user(user)
        total = self.repo.count_org_adoption_applications(org.id, q, status_value)
        rows = self.repo.list_org_adoption_applications(org.id, q, status_value, limit, offset)
        items = [self._org_incoming_adoption_item(r, org.id) for r in rows]
        return s.OrgIncomingAdoptionListResponse(total=total, items=items)

    def get_org_incoming_adoption(self, user: User, application_id: int) -> s.OrgIncomingAdoptionItem:
        org = self._organization_for_user(user)
        r = self.repo.get_org_adoption_application(org.id, application_id)
        if r is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        return self._org_incoming_adoption_item(r, org.id)

    def approve_org_incoming_adoption(self, user: User, application_id: int) -> s.OrgIncomingAdoptionItem:
        org = self._organization_for_user(user)
        row = self.repo.get_org_adoption_application(org.id, application_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        if row.status != AdoptionApplicationStatus.PENDING_REVIEW.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Заявка уже обработана")
        row.status = AdoptionApplicationStatus.APPROVED.value
        row.updated_at = datetime.utcnow()
        self.repo.db.commit()
        return self.get_org_incoming_adoption(user, application_id)

    def reject_org_incoming_adoption(
        self, user: User, application_id: int, payload: s.OrgIncomingRejectRequest
    ) -> s.OrgIncomingAdoptionItem:
        org = self._organization_for_user(user)
        row = self.repo.get_org_adoption_application(org.id, application_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        if row.status != AdoptionApplicationStatus.PENDING_REVIEW.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Заявка уже обработана")
        row.status = AdoptionApplicationStatus.REJECTED.value
        reason = (payload.reason or "").strip()
        if reason:
            row.message = reason
        row.updated_at = datetime.utcnow()
        self.repo.db.commit()
        return self.get_org_incoming_adoption(user, application_id)

    def list_org_incoming_volunteer_responses(
        self, user: User, q: str | None, status_value: str | None, limit: int, offset: int
    ) -> s.OrgIncomingVolunteerResponseListResponse:
        org = self._organization_for_user(user)
        total = self.repo.count_org_volunteer_responses(org.id, q, status_value)
        rows = self.repo.list_org_volunteer_responses(org.id, q, status_value, limit, offset)
        items = [
            s.OrgIncomingVolunteerResponseItem(
                id=r.id,
                volunteer_user_id=r.volunteer_user_id,
                volunteer_name=(r.volunteer.full_name if r.volunteer else None) or f"Волонтёр #{r.volunteer_user_id}",
                help_request_id=r.help_request_id,
                help_request_title=r.help_request.title if r.help_request else "?",
                created_at=r.created_at,
                status=r.status,
                status_label=s.VOLUNTEER_RESPONSE_STATUS_LABELS.get(r.status, r.status),
                message=r.message,
            )
            for r in rows
        ]
        return s.OrgIncomingVolunteerResponseListResponse(total=total, items=items)

    def get_org_incoming_volunteer_response(self, user: User, response_id: int) -> s.OrgIncomingVolunteerResponseItem:
        org = self._organization_for_user(user)
        r = self.repo.get_org_volunteer_response(org.id, response_id)
        if r is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        return s.OrgIncomingVolunteerResponseItem(
            id=r.id,
            volunteer_user_id=r.volunteer_user_id,
            volunteer_name=(r.volunteer.full_name if r.volunteer else None) or f"Волонтёр #{r.volunteer_user_id}",
            help_request_id=r.help_request_id,
            help_request_title=r.help_request.title if r.help_request else "?",
            created_at=r.created_at,
            status=r.status,
            status_label=s.VOLUNTEER_RESPONSE_STATUS_LABELS.get(r.status, r.status),
            message=r.message,
        )

    def accept_org_incoming_volunteer_response(self, user: User, response_id: int) -> s.OrgIncomingVolunteerResponseItem:
        org = self._organization_for_user(user)
        r = self.repo.get_org_volunteer_response(org.id, response_id)
        if r is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        if r.status != VolunteerHelpResponseStatus.PENDING.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отклик уже обработан")
        r.status = VolunteerHelpResponseStatus.ACCEPTED.value
        r.updated_at = datetime.utcnow()
        self._ensure_volunteer_response_dialog(org, r)
        self.repo.db.commit()
        return self.get_org_incoming_volunteer_response(user, response_id)

    def reject_org_incoming_volunteer_response(
        self, user: User, response_id: int, payload: s.OrgIncomingRejectRequest
    ) -> s.OrgIncomingVolunteerResponseItem:
        org = self._organization_for_user(user)
        r = self.repo.get_org_volunteer_response(org.id, response_id)
        if r is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отклик не найден")
        if r.status != VolunteerHelpResponseStatus.PENDING.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отклик уже обработан")
        r.status = VolunteerHelpResponseStatus.REJECTED.value
        reason = (payload.reason or "").strip()
        if reason:
            r.message = reason
        r.updated_at = datetime.utcnow()
        self.repo.db.commit()
        return self.get_org_incoming_volunteer_response(user, response_id)

    def _ensure_volunteer_response_dialog(self, org, response: VolunteerHelpResponse) -> None:
        hr = response.help_request
        title = f"Отклик волонтёра: {hr.title if hr else 'Задача'}"
        existing = self.repo.find_org_dialog_by_org_and_participant(org.id, response.volunteer_user_id)
        if existing is not None:
            if not existing.context_title:
                existing.context_title = title
            if hr and existing.context_entity_id is None:
                existing.context_entity_id = hr.id
                existing.context_type = "volunteer_response"
            return
        volunteer = self.repo.get_user_by_id_with_profiles(response.volunteer_user_id)
        if volunteer is None:
            return
        avatar: str | None = None
        if volunteer.volunteer_profile and volunteer.volunteer_profile.avatar_path:
            avatar = volunteer.volunteer_profile.avatar_path
        self.repo.db.add(
            OrgChatDialog(
                organization_id=org.id,
                participant_user_id=volunteer.id,
                participant_name=volunteer.full_name or f"Волонтёр #{volunteer.id}",
                participant_avatar_path=avatar,
                context_type="volunteer_response",
                context_entity_id=hr.id if hr else None,
                context_title=title,
                unread_count_org=0,
                unread_count_volunteer=0,
                unread_count_user=0,
            )
        )

    def _chat_thread_id_for_participant(
        self, organization_id: int | None, participant_user_id: int
    ) -> str | None:
        if organization_id is None:
            return None
        dialog = self.repo.find_org_dialog_by_org_and_participant(organization_id, participant_user_id)
        return str(dialog.id) if dialog is not None else None

    def _participant_display(self, participant: User) -> tuple[str, str | None]:
        name = participant.full_name or f"Участник #{participant.id}"
        avatar: str | None = None
        if participant.user_profile and participant.user_profile.avatar_path:
            avatar = participant.user_profile.avatar_path
        elif participant.volunteer_profile and participant.volunteer_profile.avatar_path:
            avatar = participant.volunteer_profile.avatar_path
        return name, avatar

    def _increment_participant_unread_after_org_message(self, dialog: OrgChatDialog) -> None:
        pid = dialog.participant_user_id
        if pid is None:
            return
        if self.repo.participant_is_volunteer(pid):
            self.repo.increment_dialog_unread_for_volunteer(dialog.id)
        elif self.repo.participant_is_user(pid):
            self.repo.increment_dialog_unread_for_user(dialog.id)

    def _ensure_participant_can_reply(self, dialog_id: int) -> None:
        if not self.repo.dialog_has_organization_message(dialog_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ответить можно только после сообщения от организации",
            )

    def _dialog_item(self, row) -> s.OrgCommsDialogItem:
        return s.OrgCommsDialogItem(
            id=row.id,
            participant_user_id=row.participant_user_id,
            participant_name=row.participant_name,
            participant_avatar_url=self._media_url(row.participant_avatar_path),
            context_type=row.context_type,
            context_entity_id=row.context_entity_id,
            context_title=row.context_title,
            last_message_preview=row.last_message_preview,
            last_message_at=row.last_message_at,
            unread_count=int(row.unread_count_org or 0),
        )

    def list_org_dialogs(
        self,
        user: User,
        q: str | None,
        limit: int,
        offset: int,
    ) -> s.OrgCommsDialogListResponse:
        org = self._organization_for_user(user)
        total, unread_total, rows = self.repo.list_org_dialogs(org.id, q, limit, offset)
        return s.OrgCommsDialogListResponse(
            total=total,
            unread_total=unread_total,
            items=[self._dialog_item(r) for r in rows],
        )

    def get_org_dialog(self, user: User, dialog_id: int) -> s.OrgCommsDialogDetail:
        org = self._organization_for_user(user)
        dialog = self.repo.get_org_dialog(org.id, dialog_id)
        if dialog is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден")
        messages = self.repo.list_org_dialog_messages(dialog.id)
        out_messages = [
            s.OrgCommsMessageItem(
                id=m.id,
                sender_user_id=m.sender_user_id,
                sender_role=m.sender_role,
                body=m.body,
                photo_url=self._media_url(m.photo_path),
                created_at=m.created_at,
                is_outgoing=(m.sender_role == UserRole.ORGANIZATION.value and m.sender_user_id == user.id),
            )
            for m in messages
        ]
        self.repo.mark_dialog_messages_read_by_org(dialog.id)
        self.repo.db.commit()
        self.repo.db.refresh(dialog)
        hint = None
        if dialog.context_title:
            hint = f"Контекст диалога: {dialog.context_title}"
        return s.OrgCommsDialogDetail(
            dialog=self._dialog_item(dialog),
            context_hint=hint,
            messages=out_messages,
        )

    @staticmethod
    def _comms_preview_text(body_plain: str, has_photo: bool) -> str:
        t = (body_plain or "").strip()
        photo_tag = " · фото"
        if t and has_photo:
            remain = 500 - len(photo_tag)
            if remain < 1:
                return photo_tag.strip()
            if len(t) > remain:
                t = t[: max(remain - 1, 1)].rstrip() + "…"
            return t + photo_tag
        if t:
            return t
        if has_photo:
            return "Фото"
        return ""

    def create_org_dialog_message(
        self,
        user: User,
        dialog_id: int,
        body: str,
        image: UploadFile | None,
    ) -> s.OrgCommsMessageItem:
        org = self._organization_for_user(user)
        dialog = self.repo.get_org_dialog(org.id, dialog_id)
        if dialog is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден")
        text_raw = body or ""
        if len(text_raw) > 8000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текст не длиннее 8000 символов")
        text = text_raw.strip()
        wants_file = image is not None and bool(getattr(image, "filename", None))
        if not text and not wants_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите текст сообщения или прикрепите изображение",
            )

        photo_path: str | None = None
        if wants_file:
            try:
                photo_path = save_org_chat_message_photo(
                    settings.media_dir,
                    org.id,
                    dialog.id,
                    image,
                    max_size_bytes=5 * 1024 * 1024,
                )
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        body_stored = text if text else ("" if photo_path else text)
        msg = self.repo.create_org_message(
            dialog_id=dialog.id,
            sender_user_id=user.id,
            sender_role=UserRole.ORGANIZATION.value,
            body=body_stored,
            photo_path=photo_path,
        )
        preview = self._comms_preview_text(body_stored, bool(photo_path))
        self.repo.update_dialog_last_message(dialog, preview, msg.created_at)
        self._increment_participant_unread_after_org_message(dialog)
        self.repo.db.commit()
        self.repo.db.refresh(msg)
        return s.OrgCommsMessageItem(
            id=msg.id,
            sender_user_id=msg.sender_user_id,
            sender_role=msg.sender_role,
            body=msg.body,
            photo_url=self._media_url(msg.photo_path),
            created_at=msg.created_at,
            is_outgoing=True,
        )

    def open_org_dialog_with_participant(
        self, user: User, payload: s.OrgCommsDialogOpenRequest
    ) -> s.OrgCommsDialogItem:
        org = self._organization_for_user(user)
        participant = self.repo.get_user_by_id_with_profiles(payload.participant_user_id)
        if participant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
        role = str(participant.role)
        if role not in (UserRole.USER.value, UserRole.VOLUNTEER.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Диалог можно открыть только с пользователем или волонтёром",
            )
        existing = self.repo.find_org_dialog_by_org_and_participant(org.id, participant.id)
        if existing is not None:
            if payload.context_title and not existing.context_title:
                existing.context_title = payload.context_title
            if payload.context_type and not existing.context_type:
                existing.context_type = payload.context_type
            if payload.context_entity_id is not None and existing.context_entity_id is None:
                existing.context_entity_id = payload.context_entity_id
            self.repo.db.commit()
            self.repo.db.refresh(existing)
            return self._dialog_item(existing)
        name, avatar = self._participant_display(participant)
        if payload.context_title:
            ctx_title = payload.context_title
            ctx_type = payload.context_type
            ctx_id = payload.context_entity_id
        elif role == UserRole.VOLUNTEER.value:
            ctx_title = "Переписка с волонтёром"
            ctx_type = "volunteer_direct"
            ctx_id = None
        else:
            ctx_title = "Переписка с пользователем"
            ctx_type = "user_direct"
            ctx_id = None
        dialog = OrgChatDialog(
            organization_id=org.id,
            participant_user_id=participant.id,
            participant_name=name,
            participant_avatar_path=avatar,
            context_type=ctx_type,
            context_entity_id=ctx_id,
            context_title=ctx_title,
            unread_count_org=0,
            unread_count_volunteer=0,
            unread_count_user=0,
        )
        self.repo.db.add(dialog)
        self.repo.db.commit()
        self.repo.db.refresh(dialog)
        return self._dialog_item(dialog)

    def open_org_dialog_for_adoption(self, user: User, application_id: int) -> s.OrgCommsDialogItem:
        org = self._organization_for_user(user)
        app_row = self.repo.get_org_adoption_application(org.id, application_id)
        if app_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
        animal_name = app_row.animal.name if app_row.animal else "подопечного"
        return self.open_org_dialog_with_participant(
            user,
            s.OrgCommsDialogOpenRequest(
                participant_user_id=app_row.user_id,
                context_type="adoption_application",
                context_entity_id=app_row.id,
                context_title=f"Анкета на {animal_name}",
            ),
        )

    def _volunteer_dialog_item(self, dialog: OrgChatDialog, org) -> s.VolCommsDialogItem:
        return s.VolCommsDialogItem(
            id=dialog.id,
            organization_id=org.id,
            organization_name=org.name,
            organization_logo_url=self._media_url(org.logo_path),
            context_type=dialog.context_type,
            context_entity_id=dialog.context_entity_id,
            context_title=dialog.context_title,
            last_message_preview=dialog.last_message_preview,
            last_message_at=dialog.last_message_at,
            unread_count=int(dialog.unread_count_volunteer or 0),
        )

    def list_volunteer_dialogs(
        self, user: User, q: str | None, limit: int, offset: int
    ) -> s.VolCommsDialogListResponse:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
        total, unread_total, rows = self.repo.list_volunteer_dialog_rows(user.id, q, limit, offset)
        return s.VolCommsDialogListResponse(
            total=total,
            unread_total=unread_total,
            items=[self._volunteer_dialog_item(d, o) for d, o in rows],
        )

    def get_volunteer_dialog(self, user: User, dialog_id: int) -> s.VolCommsDialogDetail:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
        row = self.repo.get_volunteer_dialog_row(user.id, dialog_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден")
        dialog, org = row
        messages = self.repo.list_org_dialog_messages(dialog.id)
        out_messages = [
            s.OrgCommsMessageItem(
                id=m.id,
                sender_user_id=m.sender_user_id,
                sender_role=m.sender_role,
                body=m.body,
                photo_url=self._media_url(m.photo_path),
                created_at=m.created_at,
                is_outgoing=(
                    m.sender_role == UserRole.VOLUNTEER.value and m.sender_user_id == user.id
                ),
            )
            for m in messages
        ]
        self.repo.mark_dialog_messages_read_by_volunteer(dialog.id)
        self.repo.db.commit()
        self.repo.db.refresh(dialog)
        hint = None
        if dialog.context_title:
            hint = f"Контекст диалога: {dialog.context_title}"
        return s.VolCommsDialogDetail(
            dialog=self._volunteer_dialog_item(dialog, org),
            context_hint=hint,
            messages=out_messages,
        )

    def create_volunteer_dialog_message(
        self,
        user: User,
        dialog_id: int,
        body: str,
        image: UploadFile | None,
    ) -> s.OrgCommsMessageItem:
        if user.role != UserRole.VOLUNTEER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
        row = self.repo.get_volunteer_dialog_row(user.id, dialog_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден")
        dialog, org = row
        self._ensure_participant_can_reply(dialog.id)
        text_raw = body or ""
        if len(text_raw) > 8000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текст не длиннее 8000 символов")
        text = text_raw.strip()
        wants_file = image is not None and bool(getattr(image, "filename", None))
        if not text and not wants_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите текст сообщения или прикрепите изображение",
            )

        photo_path: str | None = None
        if wants_file:
            try:
                photo_path = save_org_chat_message_photo(
                    settings.media_dir,
                    org.id,
                    dialog.id,
                    image,
                    max_size_bytes=5 * 1024 * 1024,
                )
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        body_stored = text if text else ("" if photo_path else text)
        msg = self.repo.create_org_message(
            dialog_id=dialog.id,
            sender_user_id=user.id,
            sender_role=UserRole.VOLUNTEER.value,
            body=body_stored,
            photo_path=photo_path,
        )
        preview = self._comms_preview_text(body_stored, bool(photo_path))
        self.repo.update_dialog_last_message(dialog, preview, msg.created_at)
        self.repo.increment_dialog_unread_for_org(dialog.id)
        self.repo.db.commit()
        self.repo.db.refresh(msg)
        return s.OrgCommsMessageItem(
            id=msg.id,
            sender_user_id=msg.sender_user_id,
            sender_role=msg.sender_role,
            body=msg.body,
            photo_url=self._media_url(msg.photo_path),
            created_at=msg.created_at,
            is_outgoing=True,
        )

    def _user_dialog_item(self, dialog: OrgChatDialog, org) -> s.UserCommsDialogItem:
        return s.UserCommsDialogItem(
            id=dialog.id,
            organization_id=org.id,
            organization_name=org.name,
            organization_logo_url=self._media_url(org.logo_path),
            context_type=dialog.context_type,
            context_entity_id=dialog.context_entity_id,
            context_title=dialog.context_title,
            last_message_preview=dialog.last_message_preview,
            last_message_at=dialog.last_message_at,
            unread_count=int(dialog.unread_count_user or 0),
        )

    def list_user_dialogs(
        self, user: User, q: str | None, limit: int, offset: int
    ) -> s.UserCommsDialogListResponse:
        if user.role != UserRole.USER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для пользователей")
        total, unread_total, rows = self.repo.list_user_dialog_rows(user.id, q, limit, offset)
        return s.UserCommsDialogListResponse(
            total=total,
            unread_total=unread_total,
            items=[self._user_dialog_item(d, o) for d, o in rows],
        )

    def get_user_dialog(self, user: User, dialog_id: int) -> s.UserCommsDialogDetail:
        if user.role != UserRole.USER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для пользователей")
        row = self.repo.get_user_dialog_row(user.id, dialog_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден")
        dialog, org = row
        messages = self.repo.list_org_dialog_messages(dialog.id)
        out_messages = [
            s.OrgCommsMessageItem(
                id=m.id,
                sender_user_id=m.sender_user_id,
                sender_role=m.sender_role,
                body=m.body,
                photo_url=self._media_url(m.photo_path),
                created_at=m.created_at,
                is_outgoing=(m.sender_role == UserRole.USER.value and m.sender_user_id == user.id),
            )
            for m in messages
        ]
        self.repo.mark_dialog_messages_read_by_user(dialog.id)
        self.repo.db.commit()
        self.repo.db.refresh(dialog)
        hint = None
        if dialog.context_title:
            hint = f"Контекст диалога: {dialog.context_title}"
        return s.UserCommsDialogDetail(
            dialog=self._user_dialog_item(dialog, org),
            context_hint=hint,
            messages=out_messages,
        )

    def create_user_dialog_message(
        self,
        user: User,
        dialog_id: int,
        body: str,
        image: UploadFile | None,
    ) -> s.OrgCommsMessageItem:
        if user.role != UserRole.USER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для пользователей")
        row = self.repo.get_user_dialog_row(user.id, dialog_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден")
        dialog, org = row
        self._ensure_participant_can_reply(dialog.id)
        text_raw = body or ""
        if len(text_raw) > 8000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текст не длиннее 8000 символов")
        text = text_raw.strip()
        wants_file = image is not None and bool(getattr(image, "filename", None))
        if not text and not wants_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите текст сообщения или прикрепите изображение",
            )

        photo_path: str | None = None
        if wants_file:
            try:
                photo_path = save_org_chat_message_photo(
                    settings.media_dir,
                    org.id,
                    dialog.id,
                    image,
                    max_size_bytes=5 * 1024 * 1024,
                )
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        body_stored = text if text else ("" if photo_path else text)
        msg = self.repo.create_org_message(
            dialog_id=dialog.id,
            sender_user_id=user.id,
            sender_role=UserRole.USER.value,
            body=body_stored,
            photo_path=photo_path,
        )
        preview = self._comms_preview_text(body_stored, bool(photo_path))
        self.repo.update_dialog_last_message(dialog, preview, msg.created_at)
        self.repo.increment_dialog_unread_for_org(dialog.id)
        self.repo.db.commit()
        self.repo.db.refresh(msg)
        return s.OrgCommsMessageItem(
            id=msg.id,
            sender_user_id=msg.sender_user_id,
            sender_role=msg.sender_role,
            body=msg.body,
            photo_url=self._media_url(msg.photo_path),
            created_at=msg.created_at,
            is_outgoing=True,
        )

    @staticmethod
    def _org_report_item(r: OrganizationReport) -> s.OrgReportItem:
        return s.OrgReportItem(
            id=r.id,
            title=r.title,
            summary=r.summary,
            body=r.body,
            detail_url=r.detail_url,
            published_at=r.published_at,
            is_published=bool(r.is_published),
        )

    def list_org_reports(self, user: User, limit: int, offset: int) -> s.OrgReportListResponse:
        org = self._organization_for_user(user)
        total, rows = self.repo.list_org_reports(org.id, limit, offset)
        return s.OrgReportListResponse(total=total, items=[self._org_report_item(r) for r in rows])

    def create_org_report(self, user: User, payload: s.OrgReportCreate) -> s.OrgReportItem:
        org = self._organization_for_user(user)
        row = OrganizationReport(
            organization_id=org.id,
            title=payload.title,
            summary=payload.summary,
            body=payload.body,
            detail_url=payload.detail_url,
            published_at=payload.published_at or datetime.utcnow(),
            is_published=payload.is_published,
        )
        self.repo.db.add(row)
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._org_report_item(row)

    def update_org_report(self, user: User, report_id: int, payload: s.OrgReportUpdate) -> s.OrgReportItem:
        org = self._organization_for_user(user)
        row = self.repo.get_org_report(org.id, report_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отчёт не найден")
        changed = False
        for field in ("title", "summary", "body", "detail_url", "published_at", "is_published"):
            value = getattr(payload, field)
            if value is not None:
                setattr(row, field, value)
                changed = True
        if not changed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._org_report_item(row)

    def delete_org_report(self, user: User, report_id: int) -> None:
        org = self._organization_for_user(user)
        row = self.repo.get_org_report(org.id, report_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отчёт не найден")
        self.repo.db.delete(row)
        self.repo.db.commit()

    def _org_home_story_item(self, row: OrganizationHomeStory) -> s.OrgHomeStoryItem:
        return s.OrgHomeStoryItem(
            id=row.id,
            animal_name=row.animal_name,
            story=row.story,
            photo_url=self._media_url(row.photo_path),
            adopted_at=row.adopted_at,
        )

    def list_org_home_stories(self, user: User, limit: int, offset: int) -> s.OrgHomeStoryListResponse:
        org = self._organization_for_user(user)
        total, rows = self.repo.list_org_home_stories(org.id, limit, offset)
        return s.OrgHomeStoryListResponse(total=total, items=[self._org_home_story_item(r) for r in rows])

    def create_org_home_story(self, user: User, payload: s.OrgHomeStoryCreate) -> s.OrgHomeStoryItem:
        org = self._organization_for_user(user)
        row = OrganizationHomeStory(
            organization_id=org.id,
            animal_name=payload.animal_name,
            story=payload.story,
            photo_path=payload.photo_path,
            adopted_at=payload.adopted_at,
        )
        self.repo.db.add(row)
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._org_home_story_item(row)

    def update_org_home_story(self, user: User, story_id: int, payload: s.OrgHomeStoryUpdate) -> s.OrgHomeStoryItem:
        org = self._organization_for_user(user)
        row = self.repo.get_org_home_story(org.id, story_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="История не найдена")
        changed = False
        for field in ("animal_name", "story", "photo_path", "adopted_at"):
            value = getattr(payload, field)
            if value is not None:
                setattr(row, field, value)
                changed = True
        if not changed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет полей для обновления")
        self.repo.db.commit()
        self.repo.db.refresh(row)
        return self._org_home_story_item(row)

    def delete_org_home_story(self, user: User, story_id: int) -> None:
        org = self._organization_for_user(user)
        row = self.repo.get_org_home_story(org.id, story_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="История не найдена")
        self.repo.db.delete(row)
        self.repo.db.commit()

    def list_org_events(self, user: User, limit: int, offset: int) -> s.OrgEventListResponse:
        org = self._organization_for_user(user)
        total, rows = self.repo.list_org_events(org.id, limit, offset)
        return s.OrgEventListResponse(
            total=total,
            items=[
                s.OrgEventItem(
                    id=r.id,
                    title=r.title,
                    city=r.city,
                    address=r.address,
                    starts_at=r.starts_at,
                    ends_at=r.ends_at,
                    is_published=bool(r.is_published),
                    is_archived=bool(r.is_archived),
                )
                for r in rows
            ],
        )

    def list_org_articles(self, user: User, limit: int, offset: int) -> s.OrgArticleListResponse:
        org = self._organization_for_user(user)
        if org.owner_user_id is None:
            return s.OrgArticleListResponse(total=0, items=[])
        total, rows = self.repo.list_org_articles(int(org.owner_user_id), limit, offset)
        return s.OrgArticleListResponse(
            total=total,
            items=[
                s.OrgArticleItem(
                    id=r.id,
                    title=r.title,
                    category=r.category,
                    read_minutes=r.read_minutes,
                    cover_url=self._media_url(r.cover_path),
                    is_published=bool(r.is_published),
                    is_archived=bool(r.is_archived),
                    created_at=r.created_at,
                )
                for r in rows
            ],
        )

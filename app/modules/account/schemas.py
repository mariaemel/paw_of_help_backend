from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.volunteers.schemas import VolunteerWeeklySlot

APPLICATION_STATUS_LABELS: dict[str, str] = {
    "pending_review": "На рассмотрении",
    "approved": "Одобрена",
    "rejected": "Отклонена",
    "withdrawn": "Отозвана",
}

VOLUNTEER_RESPONSE_STATUS_LABELS: dict[str, str] = {
    "pending": "На рассмотрении",
    "accepted": "В работе",
    "completed": "Завершено",
    "rejected": "Отклонено",
    "withdrawn": "Отменено",
}


class MeUserBrief(BaseModel):
    id: int
    email: EmailStr
    phone: str | None = None
    full_name: str | None = None
    role: str
    is_email_verified: bool
    is_phone_verified: bool

    model_config = ConfigDict(from_attributes=True)


class MeUserProfileOut(BaseModel):
    avatar_url: str | None = None


class MeVolunteerProfileOut(BaseModel):
    about_me: str | None = None
    availability: str | None = None
    location_city: str | None = None
    location_district: str | None = None
    travel_radius_km: int | None = None
    help_format: str | None = None
    has_veterinary_education: bool = False
    weekly_availability: list[VolunteerWeeklySlot] = Field(default_factory=list)
    accepts_night_urgency: bool = False
    travel_area_mode: str | None = None
    animal_types: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    competency_slugs: list[str] = Field(default_factory=list)
    competency_labels: list[str] = Field(default_factory=list)
    is_available: bool = True
    has_own_transport: bool = False
    can_travel_other_area: bool = True
    latitude: float | None = None
    longitude: float | None = None
    avatar_url: str | None = None


class MeProfileResponse(BaseModel):
    user: MeUserBrief
    user_profile: MeUserProfileOut | None = None
    volunteer_profile: MeVolunteerProfileOut | None = None


class UserRoleProfilePatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)


class VolunteerSelfPatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    about_me: str | None = Field(default=None, max_length=8000)
    availability: str | None = Field(default=None, max_length=5000)
    location_city: str | None = Field(default=None, max_length=120)
    location_district: str | None = Field(default=None, max_length=120)
    travel_radius_km: int | None = Field(default=None, ge=0, le=5000)
    help_format: str | None = Field(default=None, max_length=24)
    has_veterinary_education: bool | None = None
    weekly_availability: list[VolunteerWeeklySlot] | None = None
    accepts_night_urgency: bool | None = None
    travel_area_mode: str | None = Field(default=None, max_length=32)
    animal_types: list[str] | None = None
    competency_slugs: list[str] | None = None
    experience_level: str | None = Field(default=None, max_length=40)
    is_available: bool | None = None
    has_own_transport: bool | None = None
    can_travel_other_area: bool | None = None
    latitude: float | None = None
    longitude: float | None = None


class OrgSelfPatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)


class MeProfilePatchRequest(BaseModel):
    user_fields: UserRoleProfilePatch | None = None
    volunteer: VolunteerSelfPatch | None = None
    organization_contact: OrgSelfPatch | None = None


class AdoptionApplicationCreate(BaseModel):
    animal_id: int
    message: str | None = Field(default=None, max_length=8000)


class AdoptionApplicationUpdate(BaseModel):
    message: str | None = Field(default=None, max_length=8000)


class AdoptionApplicationListItem(BaseModel):
    id: int
    status: str
    status_label: str
    animal_id: int
    animal_name: str
    species_label: str
    breed: str | None
    age_label: str
    primary_photo_url: str | None
    organization_name: str | None
    created_at: datetime
    updated_at: datetime


class AdoptionApplicationDetail(AdoptionApplicationListItem):
    message: str | None = None


class AdoptionApplicationListResponse(BaseModel):
    total: int
    items: list[AdoptionApplicationListItem]


class VolunteerHelpResponseCreate(BaseModel):
    help_request_id: int
    message: str | None = Field(default=None, max_length=8000)


class VolunteerHelpResponseUpdate(BaseModel):
    message: str | None = Field(default=None, max_length=8000)


class VolunteerResponseCard(BaseModel):
    id: int
    status: str
    status_label: str
    report_awaiting_org_review: bool = False
    help_request_id: int
    title: str
    description_snippet: str
    organization_id: int | None = None
    organization_name: str | None = None
    city: str | None = None
    help_type: str
    help_type_label: str | None = None
    is_urgent: bool
    volunteer_needed: bool
    deadline_at: datetime | None = None
    deadline_label: str | None = None
    created_at: datetime
    updated_at: datetime
    can_chat: bool = True
    can_cancel_response: bool = False
    can_send_report: bool = False
    can_view_report: bool = False
    chat_thread_id: str | None = Field(
        default=None,
        description="Заглушка до модуля чатов; всегда null",
    )


class VolunteerResponseDetail(VolunteerResponseCard):
    message: str | None = None
    help_request_description: str


class VolunteerHelpResponseListResponse(BaseModel):
    total: int
    items: list[VolunteerResponseCard]


class VolunteerReportCreate(BaseModel):
    content: str = Field(min_length=10, max_length=16000)


class VolunteerReportOut(BaseModel):
    id: int
    volunteer_help_response_id: int
    content: str
    submitted_at: datetime
    org_accepted_at: datetime | None = None
    org_rejection_reason: str | None = None


class AvatarUploadResponse(BaseModel):
    avatar_url: str


class OrgCommsDialogItem(BaseModel):
    id: int
    participant_name: str
    participant_avatar_url: str | None = None
    context_type: str | None = None
    context_entity_id: int | None = None
    context_title: str | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0


class OrgCommsDialogListResponse(BaseModel):
    total: int
    unread_total: int = 0
    items: list[OrgCommsDialogItem]


class OrgCommsMessageItem(BaseModel):
    id: int
    sender_user_id: int | None = None
    sender_role: str
    body: str
    photo_url: str | None = None
    created_at: datetime
    is_outgoing: bool = False


class OrgCommsDialogDetail(BaseModel):
    dialog: OrgCommsDialogItem
    context_hint: str | None = None
    messages: list[OrgCommsMessageItem]


class OrgSocialLinkIn(BaseModel):
    platform: Literal["vk", "telegram", "whatsapp"] = Field(description="vk | telegram | whatsapp")
    url: str = Field(min_length=3, max_length=500)


class OrgCabinetProfileOut(BaseModel):
    name: str | None = None
    specialization: str | None = None
    description: str | None = None
    city: str | None = None
    logo_url: str | None = None
    cover_url: str | None = None


class OrgCabinetContactsOut(BaseModel):
    phone: str | None = None
    email: str | None = None
    social_platform_options: list[str] = Field(default_factory=lambda: ["vk", "telegram", "whatsapp"])
    social_links: list[OrgSocialLinkIn] = Field(default_factory=list)


class OrgGalleryImageItem(BaseModel):
    url: str
    description: str | None = None


class OrgCabinetAboutOut(BaseModel):
    history: str | None = None
    gallery: list[OrgGalleryImageItem] = Field(default_factory=list)
    inn: str | None = None
    ogrn: str | None = None
    bank_account: str | None = None


class OrgCabinetInstructionsOut(BaseModel):
    adoption_howto: str | None = None
    admission_rules: str | None = None


class OrgCabinetProfileResponse(BaseModel):
    profile: OrgCabinetProfileOut
    contacts: OrgCabinetContactsOut
    about: OrgCabinetAboutOut
    instructions: OrgCabinetInstructionsOut


class OrgCabinetProfilePatch(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=3000)
    city: str | None = Field(default=None, max_length=120)


class OrgCabinetContactsPatch(BaseModel):
    phone: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    social_links: list[OrgSocialLinkIn] | None = None


class OrgGalleryImagePatch(BaseModel):
    url: str
    description: str | None = Field(default=None, max_length=500)


class OrgCabinetAboutPatch(BaseModel):
    history: str | None = Field(default=None, max_length=3000)
    gallery: list[OrgGalleryImagePatch] | None = None
    inn: str | None = Field(default=None, max_length=32)
    ogrn: str | None = Field(default=None, max_length=32)
    bank_account: str | None = Field(default=None, max_length=64)


class OrgCabinetInstructionsPatch(BaseModel):
    adoption_howto: str | None = Field(default=None, max_length=2000)
    admission_rules: str | None = Field(default=None, max_length=2000)


class OrgCabinetProfilePatchRequest(BaseModel):
    profile: OrgCabinetProfilePatch | None = None
    contacts: OrgCabinetContactsPatch | None = None
    about: OrgCabinetAboutPatch | None = None
    instructions: OrgCabinetInstructionsPatch | None = None


class OrgIncomingAdoptionItem(BaseModel):
    id: int
    applicant_user_id: int
    applicant_name: str
    applicant_email: str
    applicant_phone: str | None = None
    animal_id: int
    animal_name: str
    created_at: datetime
    status: str
    status_label: str
    message: str | None = None


class OrgIncomingAdoptionListResponse(BaseModel):
    total: int
    items: list[OrgIncomingAdoptionItem]


class OrgIncomingVolunteerResponseItem(BaseModel):
    id: int
    volunteer_user_id: int
    volunteer_name: str
    help_request_id: int
    help_request_title: str
    created_at: datetime
    status: str
    status_label: str
    message: str | None = None


class OrgIncomingVolunteerResponseListResponse(BaseModel):
    total: int
    items: list[OrgIncomingVolunteerResponseItem]


class OrgIncomingRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class OrgOwnedAnimalItem(BaseModel):
    id: int
    name: str
    species: str
    age_months: int
    status: str
    is_urgent: bool = False
    primary_photo_url: str | None = None
    created_at: datetime


class OrgOwnedAnimalListResponse(BaseModel):
    total: int
    items: list[OrgOwnedAnimalItem]


class OrgOwnedAnimalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    species: str = Field(default="cat", max_length=20)
    sex: str = Field(default="unknown", max_length=20)
    age_months: int = Field(default=0, ge=0, le=600)
    breed: str | None = Field(default=None, max_length=120)
    status: str = Field(default="looking_for_home", max_length=40)
    full_description: str | None = Field(default=None, max_length=8000)
    location_city: str | None = Field(default=None, max_length=120)
    is_urgent: bool = False


class OrgOwnedAnimalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = Field(default=None, max_length=40)
    age_months: int | None = Field(default=None, ge=0, le=600)
    breed: str | None = Field(default=None, max_length=120)
    full_description: str | None = Field(default=None, max_length=8000)
    location_city: str | None = Field(default=None, max_length=120)
    is_urgent: bool | None = None


class OrgOwnedHelpRequestItem(BaseModel):
    id: int
    title: str
    description: str = Field(description="Полный текст описания заявки (как в макете карточки)")
    type_group: str = Field(description="fundraising | volunteer_task")
    help_type: str
    animal_id: int | None = None
    animal_name: str | None = None
    status: str
    is_urgent: bool
    target_amount: float | None = None
    deadline_at: datetime | None = None
    deadline_note: str | None = None
    created_at: datetime


class OrgOwnedHelpRequestListResponse(BaseModel):
    total: int
    items: list[OrgOwnedHelpRequestItem]


class OrgReportItem(BaseModel):
    id: int
    title: str
    summary: str | None = None
    body: str | None = None
    detail_url: str | None = None
    published_at: datetime
    is_published: bool


class OrgReportListResponse(BaseModel):
    total: int
    items: list[OrgReportItem]


class OrgReportCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    summary: str | None = Field(default=None, max_length=600)
    body: str | None = None
    detail_url: str | None = Field(default=None, max_length=2048)
    published_at: datetime | None = None
    is_published: bool = True


class OrgReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    summary: str | None = Field(default=None, max_length=600)
    body: str | None = None
    detail_url: str | None = Field(default=None, max_length=2048)
    published_at: datetime | None = None
    is_published: bool | None = None


class OrgHomeStoryItem(BaseModel):
    id: int
    animal_name: str
    story: str
    photo_url: str | None = None
    adopted_at: date


class OrgHomeStoryListResponse(BaseModel):
    total: int
    items: list[OrgHomeStoryItem]


class OrgHomeStoryCreate(BaseModel):
    animal_name: str = Field(min_length=1, max_length=120)
    story: str = Field(min_length=5)
    photo_path: str | None = Field(default=None, max_length=500)
    adopted_at: date


class OrgHomeStoryUpdate(BaseModel):
    animal_name: str | None = Field(default=None, min_length=1, max_length=120)
    story: str | None = Field(default=None, min_length=5)
    photo_path: str | None = Field(default=None, max_length=500)
    adopted_at: date | None = None


class OrgAssetUploadResponse(BaseModel):
    url: str
    gallery: list[OrgGalleryImageItem] = Field(default_factory=list)


class OrgEventItem(BaseModel):
    id: int
    title: str
    city: str | None = None
    address: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    is_published: bool
    is_archived: bool


class OrgEventListResponse(BaseModel):
    total: int
    items: list[OrgEventItem]


class OrgArticleItem(BaseModel):
    id: int
    title: str
    category: str
    read_minutes: int
    is_published: bool
    is_archived: bool
    created_at: datetime


class OrgArticleListResponse(BaseModel):
    total: int
    items: list[OrgArticleItem]

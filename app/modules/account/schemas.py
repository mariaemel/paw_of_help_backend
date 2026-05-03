from datetime import datetime

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

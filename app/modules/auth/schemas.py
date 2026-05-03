from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    credential: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class RegisterPayloadBase(BaseModel):
    contact: str = Field(min_length=5, max_length=320, description="E-mail или номер телефона")
    full_name: str = Field(min_length=1, max_length=255, description="Имя (для организации — контактное лицо, если нужно)")
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)
    consent_personal_data: Literal[True] = Field(
        description="Согласие на обработку ПДн (должно быть true)",
    )

    @model_validator(mode="after")
    def passwords_and_consent(self):
        if self.password != self.password_confirmation:
            raise ValueError("Пароли не совпадают")
        return self


class RegisterUserRequest(RegisterPayloadBase):
    pass


class RegisterVolunteerRequest(RegisterPayloadBase):
    location_city: str | None = Field(default=None, max_length=120, description="Город")
    has_own_transport: bool = False
    can_travel_other_area: bool = True
    availability: str | None = Field(default=None, max_length=5000)
    travel_radius_km: int | None = Field(default=None, ge=0, le=5000)


class OrganizationContactInput(BaseModel):
    contact_type: str = Field(min_length=2, max_length=50)
    value: str = Field(min_length=3, max_length=255)
    note: str | None = Field(default=None, max_length=255)


class OrganizationVerificationInput(BaseModel):
    documents_url: str | None = Field(default=None, max_length=500)
    comment: str | None = Field(default=None, max_length=5000)


class RegisterOrganizationRequest(RegisterPayloadBase):
    display_name: str = Field(min_length=2, max_length=255, description="Название организации")
    organization_type: str = Field(min_length=2, max_length=255, description="Тип организации")
    city: str = Field(min_length=1, max_length=120, description="Город")
    request_verification: bool = Field(
        default=False,
        description="Запросить верификацию (как переключатель в макете)",
    )
    legal_name: str | None = Field(default=None, max_length=255)
    work_territory: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    admission_rules: str | None = Field(default=None, max_length=8000)
    contacts: list[OrganizationContactInput] = Field(default_factory=list)
    verification: OrganizationVerificationInput | None = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    phone: str | None = None
    full_name: str | None = None
    role: str
    is_email_verified: bool
    is_phone_verified: bool
    personal_data_consent_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RegisterResponse(BaseModel):
    user: UserResponse
    email_verification_token: str
    phone_verification_token: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)


class VerifyPhoneRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)

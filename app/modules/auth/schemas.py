from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterCredentials(BaseModel):
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class RegisterUserRequest(RegisterCredentials):
    bio: str | None = Field(default=None, max_length=5000)


class RegisterVolunteerRequest(RegisterCredentials):
    skills: str | None = Field(default=None, max_length=5000)
    experience: str | None = Field(default=None, max_length=5000)
    availability: str | None = Field(default=None, max_length=5000)
    location_city: str | None = Field(default=None, max_length=120)
    travel_radius_km: int | None = Field(default=None, ge=0, le=5000)
    preferred_help_format: str | None = Field(default=None, max_length=120)
    animal_categories: str | None = Field(default=None, max_length=5000)


class OrganizationContactInput(BaseModel):
    contact_type: str = Field(min_length=2, max_length=50)
    value: str = Field(min_length=3, max_length=255)
    note: str | None = Field(default=None, max_length=255)


class OrganizationVerificationInput(BaseModel):
    documents_url: str | None = Field(default=None, max_length=500)
    comment: str | None = Field(default=None, max_length=5000)


class RegisterOrganizationRequest(RegisterCredentials):
    display_name: str = Field(min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    specialization: str | None = Field(default=None, max_length=255)
    work_territory: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    admission_rules: str | None = Field(default=None, max_length=8000)
    contacts: list[OrganizationContactInput] = Field(default_factory=list)
    verification: OrganizationVerificationInput | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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

    model_config = ConfigDict(from_attributes=True)


class RegisterResponse(BaseModel):
    user: UserResponse
    email_verification_token: str
    phone_verification_token: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)


class VerifyPhoneRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)

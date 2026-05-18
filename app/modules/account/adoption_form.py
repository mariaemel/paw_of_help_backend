from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.adoption_application import AnimalAdoptionApplication

HousingType = Literal["apartment", "house"]
HousingOwnership = Literal["own", "rented"]

_ADOPTION_FORM_FIELD_NAMES: tuple[str, ...] = (
    "applicant_name",
    "applicant_age",
    "applicant_phone",
    "applicant_email",
    "housing_type",
    "housing_ownership",
    "residents_consent",
    "has_children",
    "has_allergy",
    "had_pets_before",
    "has_pets_now",
    "pet_experience",
    "why_now",
    "who_looking_for",
    "ready_for_vet_costs",
    "feeding_plan",
    "ready_for_vaccination",
    "time_to_devote",
    "vacation_care",
    "return_plan",
    "ready_to_sign_contract",
    "ready_to_show_conditions",
    "ready_to_keep_in_touch",
)


class AdoptionApplicationFormBody(BaseModel):
    applicant_name: str = Field(min_length=1, max_length=120)
    applicant_age: int = Field(ge=0, le=120)
    applicant_phone: str = Field(min_length=5, max_length=32)
    applicant_email: EmailStr
    housing_type: HousingType
    housing_ownership: HousingOwnership
    residents_consent: bool
    has_children: bool
    has_allergy: bool
    had_pets_before: bool
    has_pets_now: bool
    pet_experience: str = Field(max_length=8000)
    why_now: str = Field(min_length=1, max_length=2000)
    who_looking_for: str = Field(min_length=1, max_length=2000)
    ready_for_vet_costs: bool
    feeding_plan: str = Field(min_length=1, max_length=500)
    ready_for_vaccination: bool
    time_to_devote: str = Field(min_length=1, max_length=500)
    vacation_care: str = Field(min_length=1, max_length=500)
    return_plan: str = Field(min_length=1, max_length=2000)
    ready_to_sign_contract: bool
    ready_to_show_conditions: bool
    ready_to_keep_in_touch: bool


class AdoptionApplicationFormRead(BaseModel):
    applicant_name: str | None = None
    applicant_age: int | None = None
    applicant_phone: str | None = None
    applicant_email: EmailStr | None = None
    housing_type: HousingType | None = None
    housing_ownership: HousingOwnership | None = None
    residents_consent: bool | None = None
    has_children: bool | None = None
    has_allergy: bool | None = None
    had_pets_before: bool | None = None
    has_pets_now: bool | None = None
    pet_experience: str | None = None
    why_now: str | None = None
    who_looking_for: str | None = None
    ready_for_vet_costs: bool | None = None
    feeding_plan: str | None = None
    ready_for_vaccination: bool | None = None
    time_to_devote: str | None = None
    vacation_care: str | None = None
    return_plan: str | None = None
    ready_to_sign_contract: bool | None = None
    ready_to_show_conditions: bool | None = None
    ready_to_keep_in_touch: bool | None = None


class AdoptionApplicationFormPatch(BaseModel):
    applicant_name: str | None = Field(default=None, min_length=1, max_length=120)
    applicant_age: int | None = Field(default=None, ge=0, le=120)
    applicant_phone: str | None = Field(default=None, min_length=5, max_length=32)
    applicant_email: EmailStr | None = None
    housing_type: HousingType | None = None
    housing_ownership: HousingOwnership | None = None
    residents_consent: bool | None = None
    has_children: bool | None = None
    has_allergy: bool | None = None
    had_pets_before: bool | None = None
    has_pets_now: bool | None = None
    pet_experience: str | None = Field(default=None, max_length=8000)
    why_now: str | None = Field(default=None, min_length=1, max_length=2000)
    who_looking_for: str | None = Field(default=None, min_length=1, max_length=2000)
    ready_for_vet_costs: bool | None = None
    feeding_plan: str | None = Field(default=None, min_length=1, max_length=500)
    ready_for_vaccination: bool | None = None
    time_to_devote: str | None = Field(default=None, min_length=1, max_length=500)
    vacation_care: str | None = Field(default=None, min_length=1, max_length=500)
    return_plan: str | None = Field(default=None, min_length=1, max_length=2000)
    ready_to_sign_contract: bool | None = None
    ready_to_show_conditions: bool | None = None
    ready_to_keep_in_touch: bool | None = None


def adoption_form_to_dict(body: AdoptionApplicationFormBody) -> dict:
    data = body.model_dump()
    data["applicant_email"] = str(data["applicant_email"])
    return data


def apply_adoption_form_patch(row: AnimalAdoptionApplication, patch: AdoptionApplicationFormPatch) -> bool:
    changed = False
    data = patch.model_dump(exclude_unset=True)
    if not data:
        return False
    for key, value in data.items():
        if key == "applicant_email" and value is not None:
            value = str(value).strip()
        if key in ("applicant_name", "applicant_phone", "pet_experience", "why_now", "who_looking_for", "feeding_plan", "time_to_devote", "vacation_care", "return_plan") and isinstance(value, str):
            value = value.strip()
        setattr(row, key, value)
        changed = True
    return changed


def adoption_form_from_row(row: AnimalAdoptionApplication) -> dict:
    out: dict = {}
    for name in _ADOPTION_FORM_FIELD_NAMES:
        val = getattr(row, name, None)
        if name == "applicant_email" and val is not None:
            val = str(val)
        out[name] = val
    return out

import secrets
from datetime import datetime

from fastapi import HTTPException, status

from app.core.config import settings
from app.core import login_throttle
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_raw_token,
    verify_password,
)
from app.models.profile import (
    OrganizationContact,
    OrganizationProfile,
    OrganizationVerification,
    OrganizationVerificationStatus,
    UserProfile,
    VolunteerProfile,
)
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.verification_token import VerificationPurpose
from app.modules.auth.contact import parse_login_contact
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterOrganizationRequest,
    RegisterResponse,
    RegisterUserRequest,
    RegisterVolunteerRequest,
    TokenPairResponse,
    UserResponse,
)


def _public_org_specialization(label: str) -> str:
    t = (label or "").lower()
    if any(x in t for x in ("кош", "кот", "фелин")):
        return "cat"
    if any(x in t for x in ("соб", "пёс", "пес", "dog")):
        return "dog"
    return "both"


class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo

    @staticmethod
    def _normalize_phone(phone: str | None) -> str | None:
        return phone.strip() if phone else None

    def _ensure_unique_credentials(self, email: str, phone: str | None) -> None:
        if self.repo.get_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Учётная запись с таким контактом уже есть")
        if phone and self.repo.get_by_phone(phone):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Телефон уже зарегистрирован")

    def _issue_verification_tokens(self, user_id: int, phone: str | None) -> tuple[str, str | None]:
        email_raw = secrets.token_urlsafe(32)
        self.repo.create_verification_token(
            user_id=user_id,
            token_hash=hash_raw_token(email_raw),
            purpose=VerificationPurpose.EMAIL.value,
            hours=settings.verification_token_expire_hours,
        )

        phone_raw: str | None = None
        if phone:
            phone_raw = secrets.token_urlsafe(32)
            self.repo.create_verification_token(
                user_id=user_id,
                token_hash=hash_raw_token(phone_raw),
                purpose=VerificationPurpose.PHONE.value,
                hours=settings.verification_token_expire_hours,
            )
        return email_raw, phone_raw

    def register_user(self, payload: RegisterUserRequest) -> RegisterResponse:
        try:
            email, phone = parse_login_contact(payload.contact)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Укажите корректный e-mail или номер телефона",
            )

        phone = self._normalize_phone(phone)
        self._ensure_unique_credentials(email, phone)
        consent_at = datetime.utcnow()

        try:
            password_hash = hash_password(payload.password)
            user = self.repo.create_user(
                email=email,
                phone=phone,
                password_hash=password_hash,
                full_name=payload.full_name.strip(),
                role=UserRole.USER,
                personal_data_consent_at=consent_at,
            )
            self.repo.db.add(UserProfile(user_id=user.id))
            email_raw, phone_raw = self._issue_verification_tokens(user.id, phone)
            self.repo.db.commit()
            self.repo.db.refresh(user)
        except Exception:
            self.repo.db.rollback()
            raise

        return RegisterResponse(
            user=UserResponse.model_validate(user),
            email_verification_token=email_raw,
            phone_verification_token=phone_raw,
        )

    def register_volunteer(self, payload: RegisterVolunteerRequest) -> RegisterResponse:
        try:
            email, phone = parse_login_contact(payload.contact)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Укажите корректный e-mail или номер телефона",
            )

        phone = self._normalize_phone(phone)
        self._ensure_unique_credentials(email, phone)
        consent_at = datetime.utcnow()

        try:
            password_hash = hash_password(payload.password)
            user = self.repo.create_user(
                email=email,
                phone=phone,
                password_hash=password_hash,
                full_name=payload.full_name.strip(),
                role=UserRole.VOLUNTEER,
                personal_data_consent_at=consent_at,
            )
            self.repo.db.add(
                VolunteerProfile(
                    user_id=user.id,
                    availability=payload.availability,
                    location_city=payload.location_city,
                    travel_radius_km=payload.travel_radius_km,
                    has_own_transport=payload.has_own_transport,
                    can_travel_other_area=payload.can_travel_other_area,
                )
            )
            email_raw, phone_raw = self._issue_verification_tokens(user.id, phone)
            self.repo.db.commit()
            self.repo.db.refresh(user)
        except Exception:
            self.repo.db.rollback()
            raise

        return RegisterResponse(
            user=UserResponse.model_validate(user),
            email_verification_token=email_raw,
            phone_verification_token=phone_raw,
        )

    def register_organization(self, payload: RegisterOrganizationRequest) -> RegisterResponse:
        try:
            email, phone = parse_login_contact(payload.contact)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Укажите корректный e-mail или номер телефона",
            )

        phone = self._normalize_phone(phone)
        self._ensure_unique_credentials(email, phone)
        consent_at = datetime.utcnow()

        try:
            password_hash = hash_password(payload.password)
            user = self.repo.create_user(
                email=email,
                phone=phone,
                password_hash=password_hash,
                full_name=payload.full_name.strip(),
                role=UserRole.ORGANIZATION,
                personal_data_consent_at=consent_at,
            )
            org_profile = OrganizationProfile(
                user_id=user.id,
                display_name=payload.display_name.strip(),
                legal_name=payload.legal_name,
                specialization=payload.organization_type.strip(),
                work_territory=payload.work_territory or payload.city.strip(),
                description=payload.description,
                admission_rules=payload.admission_rules,
            )
            self.repo.db.add(org_profile)
            self.repo.db.flush()

            for contact in payload.contacts:
                self.repo.db.add(
                    OrganizationContact(
                        organization_id=org_profile.id,
                        contact_type=contact.contact_type,
                        value=contact.value,
                        note=contact.note,
                    )
                )

            if payload.request_verification or payload.verification:
                pv = payload.verification
                self.repo.db.add(
                    OrganizationVerification(
                        organization_id=org_profile.id,
                        status=OrganizationVerificationStatus.PENDING.value,
                        documents_url=pv.documents_url if pv else None,
                        comment=pv.comment if pv else None,
                    )
                )

            org_spec = _public_org_specialization(payload.organization_type)
            self.repo.db.add(
                Organization(
                    owner_user_id=user.id,
                    name=payload.display_name.strip(),
                    city=payload.city.strip(),
                    specialization=org_spec,
                    description=payload.description,
                    needs_json="[]",
                )
            )

            email_raw, phone_raw = self._issue_verification_tokens(user.id, phone)
            self.repo.db.commit()
            self.repo.db.refresh(user)
        except Exception:
            self.repo.db.rollback()
            raise

        return RegisterResponse(
            user=UserResponse.model_validate(user),
            email_verification_token=email_raw,
            phone_verification_token=phone_raw,
        )

    def verify_email(self, token: str) -> UserResponse:
        token_row = self.repo.consume_verification_token(
            token_hash=hash_raw_token(token), purpose=VerificationPurpose.EMAIL.value
        )
        if not token_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

        self.repo.set_email_verified(token_row.user_id, True)
        user = self.repo.get_by_id(token_row.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserResponse.model_validate(user)

    def verify_phone(self, token: str) -> UserResponse:
        token_row = self.repo.consume_verification_token(
            token_hash=hash_raw_token(token), purpose=VerificationPurpose.PHONE.value
        )
        if not token_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

        self.repo.set_phone_verified(token_row.user_id, True)
        user = self.repo.get_by_id(token_row.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserResponse.model_validate(user)

    def login(self, payload: LoginRequest, client_host: str | None) -> TokenPairResponse:
        try:
            email, phone = parse_login_contact(payload.credential.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Некорректный e-mail или телефон",
            )
        throttle_key = login_throttle.throttle_key(client_host, f"{email}|{phone or ''}")
        login_throttle.enforce_not_locked(throttle_key)

        user = self.repo.get_by_email(email)
        if user is None and phone:
            user = self.repo.get_by_phone(phone)

        if user is None or not verify_password(payload.password, user.password_hash):
            login_throttle.record_failure(throttle_key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

        login_throttle.clear_failures(throttle_key)

        uid = str(user.id)
        role = user.role.value
        access_token = create_access_token(uid, role=role)
        refresh_token = create_refresh_token(uid, role=role)
        return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)

    def refresh(self, refresh_token: str) -> TokenPairResponse:
        try:
            payload = decode_token(refresh_token)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

        user = self.repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        uid = str(user.id)
        role = user.role.value
        return TokenPairResponse(
            access_token=create_access_token(uid, role=role),
            refresh_token=create_refresh_token(uid, role=role),
        )

    def me(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)

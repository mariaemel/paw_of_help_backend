import secrets

from fastapi import HTTPException, status

from app.core.config import settings
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
    UserProfile,
    VolunteerProfile,
)
from app.models.user import User, UserRole
from app.models.verification_token import VerificationPurpose
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


class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo

    def _normalize_phone(self, phone: str | None) -> str | None:
        return phone.strip() if phone else None

    def _ensure_unique_credentials(self, email: str, phone: str | None) -> None:
        if self.repo.get_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
        if phone and self.repo.get_by_phone(phone):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already exists")

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
        phone = self._normalize_phone(payload.phone)
        self._ensure_unique_credentials(payload.email, phone)

        try:
            password_hash = hash_password(payload.password)
            user = self.repo.create_user(
                email=payload.email,
                phone=phone,
                password_hash=password_hash,
                full_name=payload.full_name,
                role=UserRole.USER,
            )
            self.repo.db.add(UserProfile(user_id=user.id, bio=payload.bio))
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
        phone = self._normalize_phone(payload.phone)
        self._ensure_unique_credentials(payload.email, phone)

        try:
            password_hash = hash_password(payload.password)
            user = self.repo.create_user(
                email=payload.email,
                phone=phone,
                password_hash=password_hash,
                full_name=payload.full_name,
                role=UserRole.VOLUNTEER,
            )
            self.repo.db.add(
                VolunteerProfile(
                    user_id=user.id,
                    skills=payload.skills,
                    experience=payload.experience,
                    availability=payload.availability,
                    location_city=payload.location_city,
                    travel_radius_km=payload.travel_radius_km,
                    preferred_help_format=payload.preferred_help_format,
                    animal_categories=payload.animal_categories,
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
        phone = self._normalize_phone(payload.phone)
        self._ensure_unique_credentials(payload.email, phone)

        try:
            password_hash = hash_password(payload.password)
            user = self.repo.create_user(
                email=payload.email,
                phone=phone,
                password_hash=password_hash,
                full_name=payload.full_name,
                role=UserRole.ORGANIZATION,
            )
            org = OrganizationProfile(
                user_id=user.id,
                display_name=payload.display_name,
                legal_name=payload.legal_name,
                specialization=payload.specialization,
                work_territory=payload.work_territory,
                description=payload.description,
                admission_rules=payload.admission_rules,
            )
            self.repo.db.add(org)
            self.repo.db.flush()

            for contact in payload.contacts:
                self.repo.db.add(
                    OrganizationContact(
                        organization_id=org.id,
                        contact_type=contact.contact_type,
                        value=contact.value,
                        note=contact.note,
                    )
                )

            if payload.verification:
                self.repo.db.add(
                    OrganizationVerification(
                        organization_id=org.id,
                        documents_url=payload.verification.documents_url,
                        comment=payload.verification.comment,
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

    def login(self, payload: LoginRequest) -> TokenPairResponse:
        user = self.repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)

    def refresh(self, refresh_token: str) -> TokenPairResponse:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

        user = self.repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return TokenPairResponse(
            access_token=create_access_token(subject=str(user.id)),
            refresh_token=create_refresh_token(subject=str(user.id)),
        )

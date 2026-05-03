from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user import UserRole
from app.models.verification_token import VerificationToken


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_phone(self, phone: str) -> User | None:
        return self.db.query(User).filter(User.phone == phone).first()

    def create_user(
        self,
        email: str,
        phone: str | None,
        password_hash: str,
        full_name: str | None,
        role: UserRole,
        personal_data_consent_at: datetime | None = None,
    ) -> User:
        user = User(
            email=email,
            phone=phone,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            personal_data_consent_at=personal_data_consent_at,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def set_email_verified(self, user_id: int, verified: bool) -> None:
        user = self.get_by_id(user_id)
        if not user:
            return
        user.is_email_verified = verified
        self.db.add(user)
        self.db.commit()

    def set_phone_verified(self, user_id: int, verified: bool) -> None:
        user = self.get_by_id(user_id)
        if not user:
            return
        user.is_phone_verified = verified
        self.db.add(user)
        self.db.commit()

    def create_verification_token(self, user_id: int, token_hash: str, purpose: str, hours: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        token = VerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            purpose=purpose,
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.flush()

    def consume_verification_token(self, token_hash: str, purpose: str) -> VerificationToken | None:
        token = (
            self.db.query(VerificationToken)
            .filter(
                VerificationToken.token_hash == token_hash,
                VerificationToken.purpose == purpose,
                VerificationToken.consumed_at.is_(None),
            )
            .order_by(VerificationToken.id.desc())
            .first()
        )
        if not token:
            return None

        if token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None

        token.consumed_at = datetime.now(timezone.utc)
        self.db.add(token)
        self.db.commit()
        return token

    def set_user_role(self, user_id: int, role: UserRole) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.role = role
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

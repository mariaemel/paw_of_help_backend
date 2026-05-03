from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterOrganizationRequest,
    RegisterResponse,
    RegisterUserRequest,
    RegisterVolunteerRequest,
    TokenPairResponse,
    TokenRefreshRequest,
    UserResponse,
    VerifyEmailRequest,
    VerifyPhoneRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


@router.post("/register/user", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterUserRequest, service: AuthService = Depends(get_auth_service)):
    return service.register_user(payload)


@router.post("/register/volunteer", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_volunteer(payload: RegisterVolunteerRequest, service: AuthService = Depends(get_auth_service)):
    return service.register_volunteer(payload)


@router.post("/register/organization", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_organization(payload: RegisterOrganizationRequest, service: AuthService = Depends(get_auth_service)):
    return service.register_organization(payload)


@router.post("/verify-email", response_model=UserResponse)
def verify_email(payload: VerifyEmailRequest, service: AuthService = Depends(get_auth_service)):
    return service.verify_email(payload.token)


@router.post("/verify-phone", response_model=UserResponse)
def verify_phone(payload: VerifyPhoneRequest, service: AuthService = Depends(get_auth_service)):
    return service.verify_phone(payload.token)


@router.post("/login", response_model=TokenPairResponse)
def login(
    request: Request,
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    host = request.client.host if request.client else None
    return service.login(payload, host)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(payload: TokenRefreshRequest, service: AuthService = Depends(get_auth_service)):
    return service.refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse)
def me(
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    return service.me(user)

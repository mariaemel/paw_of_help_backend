from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenPairResponse,
    TokenRefreshRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    return service.register(payload)


@router.post("/login", response_model=TokenPairResponse)
def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return service.login(payload)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh(payload: TokenRefreshRequest, service: AuthService = Depends(get_auth_service)):
    return service.refresh(payload.refresh_token)

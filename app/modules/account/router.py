from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.modules.account.repository import AccountRepository
from app.modules.account import schemas as s
from app.modules.account.service import AccountService

router = APIRouter(prefix="/me", tags=["profile"])


def get_account_service(db: Session = Depends(get_db)) -> AccountService:
    return AccountService(AccountRepository(db))


def require_user_or_volunteer(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.USER, UserRole.VOLUNTEER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступно пользователям и волонтёрам",
        )
    return user


def require_volunteer_role(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.VOLUNTEER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для волонтёров")
    return user


@router.get("/profile", response_model=s.MeProfileResponse)
def get_my_profile(
    user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    return service.get_profile(user)


@router.patch("/profile", response_model=s.MeProfileResponse)
def patch_my_profile(
    payload: s.MeProfilePatchRequest,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    return service.patch_profile(user, payload)


@router.post("/profile/avatar", response_model=s.AvatarUploadResponse)
def upload_my_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
):
    return service.upload_avatar(user, file)


@router.get("/applications", response_model=s.AdoptionApplicationListResponse)
def list_my_applications(
    q: str | None = Query(default=None, description="Поиск по имени животного"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_user_or_volunteer),
    service: AccountService = Depends(get_account_service),
):
    return service.list_applications(user, q, limit, offset)


@router.post("/applications", response_model=s.AdoptionApplicationDetail, status_code=status.HTTP_201_CREATED)
def create_my_application(
    payload: s.AdoptionApplicationCreate,
    user: User = Depends(require_user_or_volunteer),
    service: AccountService = Depends(get_account_service),
):
    return service.create_application(user, payload)


@router.get("/applications/{application_id}", response_model=s.AdoptionApplicationDetail)
def get_my_application(
    application_id: int,
    user: User = Depends(require_user_or_volunteer),
    service: AccountService = Depends(get_account_service),
):
    return service.get_application(user, application_id)


@router.patch("/applications/{application_id}", response_model=s.AdoptionApplicationDetail)
def update_my_application(
    application_id: int,
    payload: s.AdoptionApplicationUpdate,
    user: User = Depends(require_user_or_volunteer),
    service: AccountService = Depends(get_account_service),
):
    return service.update_application(user, application_id, payload)


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_application(
    application_id: int,
    user: User = Depends(require_user_or_volunteer),
    service: AccountService = Depends(get_account_service),
):
    service.delete_application(user, application_id)


@router.get("/volunteer/responses", response_model=s.VolunteerHelpResponseListResponse)
def list_my_volunteer_responses(
    q: str | None = Query(default=None, description="Поиск по заголовку или описанию заявки"),
    tab: Literal["all", "pending", "in_progress", "completed", "archive"] = Query(
        default="all",
        description="Фильтр: all | pending | in_progress | completed | archive",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_volunteer_responses(user, q, tab, limit, offset)


@router.post(
    "/volunteer/responses",
    response_model=s.VolunteerResponseDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_my_volunteer_response(
    payload: s.VolunteerHelpResponseCreate,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_volunteer_response(user, payload)


@router.get("/volunteer/responses/{response_id}", response_model=s.VolunteerResponseDetail)
def get_my_volunteer_response(
    response_id: int,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_volunteer_response(user, response_id)


@router.patch("/volunteer/responses/{response_id}", response_model=s.VolunteerResponseDetail)
def update_my_volunteer_response(
    response_id: int,
    payload: s.VolunteerHelpResponseUpdate,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.update_volunteer_response(user, response_id, payload)


@router.post("/volunteer/responses/{response_id}/cancel", response_model=s.VolunteerResponseDetail)
def cancel_my_volunteer_response(
    response_id: int,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    """Отменить отклик (только «На рассмотрении»)."""
    return service.withdraw_volunteer_response(user, response_id)


@router.post("/volunteer/responses/{response_id}/report", response_model=s.VolunteerResponseDetail)
def submit_my_volunteer_response_report(
    response_id: int,
    payload: s.VolunteerReportCreate,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    """Отправить или обновить отчёт (только «В работе»)."""
    return service.submit_volunteer_response_report(user, response_id, payload)


@router.get("/volunteer/responses/{response_id}/report", response_model=s.VolunteerReportOut)
def get_my_volunteer_response_report(
    response_id: int,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    """Просмотр отчёта (завершённые отклики)."""
    return service.get_volunteer_response_report(user, response_id)

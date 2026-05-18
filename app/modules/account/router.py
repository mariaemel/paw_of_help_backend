from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.modules.account.repository import AccountRepository
from app.modules.account import schemas as s
from app.modules.account.service import AccountService
from app.modules.organizations.schemas import OrganizationPublicPage
from app.modules.urgent.schemas import UrgentRequestCreate, UrgentRequestDetail, UrgentRequestUpdate

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


def require_plain_user_role(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для пользователей")
    return user


def require_organization_role(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ORGANIZATION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для организаций")
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
    return service.withdraw_volunteer_response(user, response_id)


@router.post("/volunteer/responses/{response_id}/report", response_model=s.VolunteerResponseDetail)
def submit_my_volunteer_response_report(
    response_id: int,
    payload: s.VolunteerReportCreate,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.submit_volunteer_response_report(user, response_id, payload)


@router.get("/volunteer/responses/{response_id}/report", response_model=s.VolunteerReportOut)
def get_my_volunteer_response_report(
    response_id: int,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_volunteer_response_report(user, response_id)


@router.get("/user/communications/dialogs", response_model=s.UserCommsDialogListResponse)
def list_user_dialogs(
    q: str | None = Query(default=None, description="Поиск по организации и контексту"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_plain_user_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_user_dialogs(user, q, limit, offset)


@router.get("/user/communications/dialogs/{dialog_id}", response_model=s.UserCommsDialogDetail)
def get_user_dialog(
    dialog_id: int,
    user: User = Depends(require_plain_user_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_user_dialog(user, dialog_id)


@router.post(
    "/user/communications/dialogs/{dialog_id}/messages",
    response_model=s.OrgCommsMessageItem,
    status_code=status.HTTP_201_CREATED,
)
def create_user_dialog_message(
    dialog_id: int,
    body: str = Form(
        default="",
        max_length=8000,
        description="Текст сообщения; можно оставить пустым, если прикреплено фото",
    ),
    image: UploadFile | None = File(
        default=None,
        description="Изображение (.jpg, .jpeg, .png, .webp), до 5 МБ",
    ),
    user: User = Depends(require_plain_user_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_user_dialog_message(user, dialog_id, body, image)


@router.get("/volunteer/communications/dialogs", response_model=s.VolCommsDialogListResponse)
def list_volunteer_dialogs(
    q: str | None = Query(default=None, description="Поиск по организации и контексту"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_volunteer_dialogs(user, q, limit, offset)


@router.get("/volunteer/communications/dialogs/{dialog_id}", response_model=s.VolCommsDialogDetail)
def get_volunteer_dialog(
    dialog_id: int,
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_volunteer_dialog(user, dialog_id)


@router.post(
    "/volunteer/communications/dialogs/{dialog_id}/messages",
    response_model=s.OrgCommsMessageItem,
    status_code=status.HTTP_201_CREATED,
)
def create_volunteer_dialog_message(
    dialog_id: int,
    body: str = Form(
        default="",
        max_length=8000,
        description="Текст сообщения; можно оставить пустым, если прикреплено фото",
    ),
    image: UploadFile | None = File(
        default=None,
        description="Изображение (.jpg, .jpeg, .png, .webp), до 5 МБ",
    ),
    user: User = Depends(require_volunteer_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_volunteer_dialog_message(user, dialog_id, body, image)


@router.post(
    "/organization/communications/dialogs",
    response_model=s.OrgCommsDialogItem,
    status_code=status.HTTP_201_CREATED,
)
def open_org_dialog_with_participant(
    payload: s.OrgCommsDialogOpenRequest,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.open_org_dialog_with_participant(user, payload)


@router.get("/organization/communications/dialogs", response_model=s.OrgCommsDialogListResponse)
def list_org_dialogs(
    q: str | None = Query(default=None, description="Поиск по имени участника и контексту"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_dialogs(user, q, limit, offset)


@router.get("/organization/communications/dialogs/{dialog_id}", response_model=s.OrgCommsDialogDetail)
def get_org_dialog(
    dialog_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_org_dialog(user, dialog_id)


@router.post(
    "/organization/communications/dialogs/{dialog_id}/messages",
    response_model=s.OrgCommsMessageItem,
    status_code=status.HTTP_201_CREATED,
)
def create_org_dialog_message(
    dialog_id: int,
    body: str = Form(
        default="",
        max_length=8000,
        description="Текст сообщения; можно оставить пустым, если прикреплено фото",
    ),
    image: UploadFile | None = File(
        default=None,
        description="Изображение (.jpg, .jpeg, .png, .webp), до 5 МБ",
    ),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_org_dialog_message(user, dialog_id, body, image)


@router.get("/organization/profile", response_model=s.OrgCabinetProfileResponse)
def get_org_profile_cabinet(
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_org_cabinet_profile(user)


@router.patch("/organization/profile", response_model=s.OrgCabinetProfileResponse)
def patch_org_profile_cabinet(
    payload: s.OrgCabinetProfilePatchRequest,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.patch_org_cabinet_profile(user, payload)


@router.get("/organization/profile/preview", response_model=OrganizationPublicPage)
def get_org_profile_preview(
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_org_public_preview(user)


@router.post("/organization/profile/logo", response_model=s.OrgAssetUploadResponse)
def upload_org_logo(
    file: UploadFile = File(...),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.upload_org_logo(user, file)


@router.post("/organization/profile/cover", response_model=s.OrgAssetUploadResponse)
def upload_org_cover(
    file: UploadFile = File(...),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.upload_org_cover(user, file)


@router.post("/organization/profile/gallery", response_model=s.OrgAssetUploadResponse)
def upload_org_gallery_image(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.upload_org_gallery_image(user, file, description)


@router.get("/organization/animals", response_model=s.OrgOwnedAnimalListResponse)
def list_org_animals(
    q: str | None = Query(default=None, description="Поиск по кличке"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_animals(user, q, limit, offset)


@router.post("/organization/animals", response_model=s.OrgOwnedAnimalItem, status_code=status.HTTP_201_CREATED)
def create_org_animal(
    payload: s.OrgOwnedAnimalCreate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_org_animal(user, payload)


@router.patch("/organization/animals/{animal_id}", response_model=s.OrgOwnedAnimalItem)
def update_org_animal(
    animal_id: int,
    payload: s.OrgOwnedAnimalUpdate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.update_org_animal(user, animal_id, payload)


@router.post("/organization/animals/{animal_id}/archive", response_model=s.OrgOwnedAnimalItem)
def archive_org_animal(
    animal_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.archive_org_animal(user, animal_id)


@router.get("/organization/incoming/adoptions", response_model=s.OrgIncomingAdoptionListResponse)
def list_org_incoming_adoptions(
    q: str | None = Query(default=None),
    status_value: str | None = Query(default="all", description="all | pending_review | approved | rejected"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_incoming_adoptions(user, q, status_value, limit, offset)


@router.get("/organization/incoming/adoptions/{application_id}", response_model=s.OrgIncomingAdoptionItem)
def get_org_incoming_adoption(
    application_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_org_incoming_adoption(user, application_id)


@router.post(
    "/organization/incoming/adoptions/{application_id}/dialog",
    response_model=s.OrgCommsDialogItem,
    status_code=status.HTTP_201_CREATED,
)
def open_org_dialog_for_adoption(
    application_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.open_org_dialog_for_adoption(user, application_id)


@router.post("/organization/incoming/adoptions/{application_id}/approve", response_model=s.OrgIncomingAdoptionItem)
def approve_org_incoming_adoption(
    application_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.approve_org_incoming_adoption(user, application_id)


@router.post("/organization/incoming/adoptions/{application_id}/reject", response_model=s.OrgIncomingAdoptionItem)
def reject_org_incoming_adoption(
    application_id: int,
    payload: s.OrgIncomingRejectRequest,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.reject_org_incoming_adoption(user, application_id, payload)


@router.get("/organization/incoming/volunteer-responses", response_model=s.OrgIncomingVolunteerResponseListResponse)
def list_org_incoming_volunteer_responses(
    q: str | None = Query(default=None),
    status_value: str | None = Query(default="all", description="all | pending | accepted | rejected | completed"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_incoming_volunteer_responses(user, q, status_value, limit, offset)


@router.get("/organization/incoming/volunteer-responses/{response_id}", response_model=s.OrgIncomingVolunteerResponseItem)
def get_org_incoming_volunteer_response(
    response_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.get_org_incoming_volunteer_response(user, response_id)


@router.post(
    "/organization/incoming/volunteer-responses/{response_id}/accept",
    response_model=s.OrgIncomingVolunteerResponseItem,
)
def accept_org_incoming_volunteer_response(
    response_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.accept_org_incoming_volunteer_response(user, response_id)


@router.post(
    "/organization/incoming/volunteer-responses/{response_id}/reject",
    response_model=s.OrgIncomingVolunteerResponseItem,
)
def reject_org_incoming_volunteer_response(
    response_id: int,
    payload: s.OrgIncomingRejectRequest,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.reject_org_incoming_volunteer_response(user, response_id, payload)


@router.get("/organization/help-requests", response_model=s.OrgOwnedHelpRequestListResponse)
def list_org_help_requests(
    q: str | None = Query(default=None),
    tab: str | None = Query(default="all", description="all | fundraising | volunteer_task"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_help_requests(user, q, tab, limit, offset)


@router.post("/organization/help-requests", response_model=UrgentRequestDetail, status_code=status.HTTP_201_CREATED)
def create_org_help_request(
    payload: UrgentRequestCreate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_org_help_request(user, payload)


@router.patch("/organization/help-requests/{request_id}", response_model=UrgentRequestDetail)
def update_org_help_request(
    request_id: int,
    payload: UrgentRequestUpdate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.update_org_help_request(user, request_id, payload)


@router.post("/organization/help-requests/{request_id}/close", response_model=UrgentRequestDetail)
def close_org_help_request(
    request_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.close_org_help_request(user, request_id)


@router.get("/organization/reports", response_model=s.OrgReportListResponse)
def list_org_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_reports(user, limit, offset)


@router.post("/organization/reports", response_model=s.OrgReportItem, status_code=status.HTTP_201_CREATED)
def create_org_report(
    payload: s.OrgReportCreate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_org_report(user, payload)


@router.patch("/organization/reports/{report_id}", response_model=s.OrgReportItem)
def update_org_report(
    report_id: int,
    payload: s.OrgReportUpdate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.update_org_report(user, report_id, payload)


@router.delete("/organization/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_report(
    report_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    service.delete_org_report(user, report_id)


@router.get("/organization/home-stories", response_model=s.OrgHomeStoryListResponse)
def list_org_home_stories(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_home_stories(user, limit, offset)


@router.post("/organization/home-stories", response_model=s.OrgHomeStoryItem, status_code=status.HTTP_201_CREATED)
def create_org_home_story(
    payload: s.OrgHomeStoryCreate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.create_org_home_story(user, payload)


@router.patch("/organization/home-stories/{story_id}", response_model=s.OrgHomeStoryItem)
def update_org_home_story(
    story_id: int,
    payload: s.OrgHomeStoryUpdate,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.update_org_home_story(user, story_id, payload)


@router.delete("/organization/home-stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_home_story(
    story_id: int,
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    service.delete_org_home_story(user, story_id)


@router.get("/organization/events", response_model=s.OrgEventListResponse)
def list_org_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_events(user, limit, offset)


@router.get("/organization/articles", response_model=s.OrgArticleListResponse)
def list_org_articles(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_organization_role),
    service: AccountService = Depends(get_account_service),
):
    return service.list_org_articles(user, limit, offset)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import (
    KnowledgeCatalogsResponse,
    KnowledgeDetail,
    KnowledgeFilterParams,
    KnowledgeListResponse,
    KnowledgeUpdateRequest,
    KnowledgeUpsertRequest,
)
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_service(db: Session = Depends(get_db)) -> KnowledgeService:
    return KnowledgeService(KnowledgeRepository(db))


@router.get("", response_model=KnowledgeListResponse)
def list_articles(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None, description="care | first_aid | adaptation | ... | all"),
    only_context_tips: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="-created_at"),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    filters = KnowledgeFilterParams(
        q=q,
        category=category,
        only_context_tips=only_context_tips,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.list_articles(filters)


@router.get("/catalogs", response_model=KnowledgeCatalogsResponse)
def knowledge_catalogs(service: KnowledgeService = Depends(get_knowledge_service)):
    return service.get_catalogs()


@router.get("/{article_id}", response_model=KnowledgeDetail)
def article_detail(article_id: int, service: KnowledgeService = Depends(get_knowledge_service)):
    return service.get_detail(article_id)


_kb_writers = require_roles(UserRole.VOLUNTEER, UserRole.ORGANIZATION)


@router.post("", response_model=KnowledgeDetail)
def create_article(
    payload: KnowledgeUpsertRequest,
    user: User = Depends(_kb_writers),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    return service.create_article(user, payload)


@router.patch("/{article_id}", response_model=KnowledgeDetail)
def update_article(
    article_id: int,
    payload: KnowledgeUpdateRequest,
    user: User = Depends(_kb_writers),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    return service.update_article(article_id, user, payload)


@router.post("/{article_id}/archive", response_model=KnowledgeDetail)
def archive_article(
    article_id: int,
    user: User = Depends(_kb_writers),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    return service.archive_article(article_id, user)


@router.delete("/{article_id}")
def delete_article(
    article_id: int,
    user: User = Depends(_kb_writers),
    service: KnowledgeService = Depends(get_knowledge_service),
):
    service.delete_article(article_id, user)
    return {"ok": True}

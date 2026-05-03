import math
import re

from fastapi import HTTPException, status

from app.models.knowledge import KnowledgeArticle
from app.models.user import User, UserRole
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import (
    KB_CATEGORY_OPTIONS,
    CatalogOption,
    KnowledgeCatalogsResponse,
    KnowledgeDetail,
    KnowledgeFilterParams,
    KnowledgeListItem,
    KnowledgeListResponse,
    KnowledgeUpdateRequest,
    KnowledgeUpsertRequest,
)

_CATEGORY_LABELS = {x["id"]: x["label"] for x in KB_CATEGORY_OPTIONS}
_AVERAGE_READING_WPM = 180
_WORD_RE = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)


class KnowledgeService:
    def __init__(self, repo: KnowledgeRepository):
        self.repo = repo

    @staticmethod
    def _ensure_writer(user: User) -> None:
        if user.role not in (UserRole.VOLUNTEER, UserRole.ORGANIZATION):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Volunteer or organization role required to manage knowledge base",
            )

    @staticmethod
    def _ensure_can_edit(article: KnowledgeArticle, user: User) -> None:
        if article.author_user_id != user.id or article.owner_role != user.role.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only edit own article")

    @staticmethod
    def _estimate_read_minutes(content: str) -> int:
        words = len(_WORD_RE.findall(content or ""))
        if words <= 0:
            return 1
        return max(1, int(math.ceil(words / _AVERAGE_READING_WPM)))

    def list_articles(self, filters: KnowledgeFilterParams) -> KnowledgeListResponse:
        total, rows = self.repo.list_articles(filters)
        items = [
            KnowledgeListItem(
                id=a.id,
                title=a.title,
                summary=a.summary,
                category=a.category,
                category_label=_CATEGORY_LABELS.get(a.category),
                read_minutes=a.read_minutes,
                is_context_tip=bool(a.is_context_tip),
                created_at=a.created_at,
            )
            for a in rows
        ]
        return KnowledgeListResponse(total=total, items=items)

    def get_catalogs(self) -> KnowledgeCatalogsResponse:
        return KnowledgeCatalogsResponse(
            categories=[CatalogOption(**x) for x in KB_CATEGORY_OPTIONS] + [CatalogOption(id="all", label="Все")],
            tip_scope_options=[
                CatalogOption(id="all", label="Все материалы"),
                CatalogOption(id="tips", label="Только контекстные подсказки"),
            ],
        )

    def get_detail(self, article_id: int) -> KnowledgeDetail:
        row = self.repo.get_article(article_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        return KnowledgeDetail(
            id=row.id,
            title=row.title,
            summary=row.summary,
            content=row.content,
            category=row.category,
            category_label=_CATEGORY_LABELS.get(row.category),
            read_minutes=row.read_minutes,
            is_context_tip=bool(row.is_context_tip),
            owner_role=row.owner_role,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create_article(self, user: User, payload: KnowledgeUpsertRequest) -> KnowledgeDetail:
        self._ensure_writer(user)
        art = KnowledgeArticle(
            author_user_id=user.id,
            owner_role=user.role.value,
            title=payload.title,
            summary=payload.summary,
            content=payload.content,
            category=payload.category,
            read_minutes=self._estimate_read_minutes(payload.content),
            is_context_tip=payload.is_context_tip,
            is_published=payload.is_published,
            is_archived=False,
        )
        self.repo.db.add(art)
        self.repo.db.commit()
        self.repo.db.refresh(art)
        return self.get_detail(art.id)

    def update_article(self, article_id: int, user: User, payload: KnowledgeUpdateRequest) -> KnowledgeDetail:
        self._ensure_writer(user)
        art = self.repo.get_article_for_owner(article_id)
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        self._ensure_can_edit(art, user)

        for field in (
            "title",
            "summary",
            "content",
            "category",
            "is_context_tip",
            "is_published",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(art, field, value)
        if payload.content is not None:
            art.read_minutes = self._estimate_read_minutes(payload.content)

        self.repo.db.commit()
        self.repo.db.refresh(art)
        return KnowledgeDetail(
            id=art.id,
            title=art.title,
            summary=art.summary,
            content=art.content,
            category=art.category,
            category_label=_CATEGORY_LABELS.get(art.category),
            read_minutes=art.read_minutes,
            is_context_tip=bool(art.is_context_tip),
            owner_role=art.owner_role,
            created_at=art.created_at,
            updated_at=art.updated_at,
        )

    def delete_article(self, article_id: int, user: User) -> None:
        self._ensure_writer(user)
        art = self.repo.get_article_for_owner(article_id)
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        self._ensure_can_edit(art, user)
        self.repo.db.delete(art)
        self.repo.db.commit()

    def archive_article(self, article_id: int, user: User) -> KnowledgeDetail:
        self._ensure_writer(user)
        art = self.repo.get_article_for_owner(article_id)
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        self._ensure_can_edit(art, user)
        art.is_archived = True
        self.repo.db.commit()
        self.repo.db.refresh(art)
        return KnowledgeDetail(
            id=art.id,
            title=art.title,
            summary=art.summary,
            content=art.content,
            category=art.category,
            category_label=_CATEGORY_LABELS.get(art.category),
            read_minutes=art.read_minutes,
            is_context_tip=bool(art.is_context_tip),
            owner_role=art.owner_role,
            created_at=art.created_at,
            updated_at=art.updated_at,
        )

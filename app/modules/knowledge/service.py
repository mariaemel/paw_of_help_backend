import math
import re

from fastapi import HTTPException, UploadFile, status

from app.core.cache import cached_model, get_json, is_enabled, set_json
from app.core.cache_keys import KNOWLEDGE_CATALOGS, knowledge_article_key
from app.core.cache_invalidation import invalidate_knowledge_article
from app.core.config import settings
from app.models.knowledge import KnowledgeArticle
from app.models.user import User, UserRole
from app.modules.knowledge.hints import HintContext, pick_hints
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.storage import save_knowledge_cover
from app.modules.knowledge.schemas import (
    KB_CATEGORY_OPTIONS,
    CatalogOption,
    KnowledgeCatalogsResponse,
    KnowledgeDetail,
    KnowledgeFilterParams,
    KnowledgeHintItem,
    KnowledgeHintRequestParams,
    KnowledgeHintsResponse,
    KnowledgeListItem,
    KnowledgeListResponse,
    KnowledgeMineItem,
    KnowledgeMineListResponse,
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
    def _cover_url(path: str | None) -> str | None:
        if not path or not str(path).strip():
            return None
        return f"{settings.media_url_prefix}/{str(path).strip().lstrip('/')}"

    @staticmethod
    def _ensure_writer(user: User) -> None:
        if user.role not in (UserRole.VOLUNTEER, UserRole.ORGANIZATION):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Volunteer or organization role required to manage knowledge base",
            )

    @staticmethod
    def _user_role_value(user: User) -> str:
        role = user.role
        return role.value if isinstance(role, UserRole) else str(role)

    @staticmethod
    def can_edit_article(article: KnowledgeArticle, user: User | None) -> bool:
        if user is None:
            return False
        if article.author_user_id is None:
            return False
        return (
            int(article.author_user_id) == int(user.id)
            and str(article.owner_role) == KnowledgeService._user_role_value(user)
        )

    @staticmethod
    def _ensure_can_edit(article: KnowledgeArticle, user: User) -> None:
        if not KnowledgeService.can_edit_article(article, user):
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
        def _load() -> KnowledgeCatalogsResponse:
            return KnowledgeCatalogsResponse(
                categories=[CatalogOption(**x) for x in KB_CATEGORY_OPTIONS]
                + [CatalogOption(id="all", label="Все")],
                tip_scope_options=[
                    CatalogOption(id="all", label="Все материалы"),
                    CatalogOption(id="tips", label="Только контекстные подсказки"),
                ],
            )

        return cached_model(
            KNOWLEDGE_CATALOGS,
            settings.cache_ttl_static_catalogs,
            KnowledgeCatalogsResponse,
            _load,
        )

    def get_detail(self, article_id: int, viewer: User | None = None) -> KnowledgeDetail:
        cache_key = knowledge_article_key(article_id)
        if is_enabled() and viewer is None:
            raw = get_json(cache_key)
            if raw is not None:
                return KnowledgeDetail.model_validate(raw)

        row = self.repo.get_article(article_id)
        if not row:
            row = self.repo.get_article_for_owner(article_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if viewer is not None and (not row.is_published or row.is_archived):
            self._ensure_can_edit(row, viewer)

        detail = self._to_detail(row, viewer)
        if (
            is_enabled()
            and row.is_published
            and not row.is_archived
            and not self.can_edit_article(row, viewer)
        ):
            set_json(cache_key, detail.model_dump(mode="json"), settings.cache_ttl_knowledge_article)
        return detail

    def list_my_articles(
        self, user: User, limit: int = 100, offset: int = 0, tab: str = "all"
    ) -> KnowledgeMineListResponse:
        self._ensure_writer(user)
        owner_role = self._user_role_value(user)
        total, rows = self.repo.list_my_articles(int(user.id), owner_role, limit, offset, tab=tab)
        items = [
            KnowledgeMineItem(
                id=a.id,
                title=a.title,
                summary=a.summary,
                cover_url=self._cover_url(a.cover_path),
                category=a.category,
                category_label=_CATEGORY_LABELS.get(a.category),
                read_minutes=a.read_minutes,
                is_context_tip=bool(a.is_context_tip),
                created_at=a.created_at,
                author_user_id=a.author_user_id,
                is_published=bool(a.is_published),
                is_archived=bool(a.is_archived),
                can_edit=True,
            )
            for a in rows
        ]
        return KnowledgeMineListResponse(total=total, items=items)

    def list_context_hints(self, params: KnowledgeHintRequestParams) -> KnowledgeHintsResponse:
        ctx = HintContext(
            help_type=params.help_type,
            animal_species=params.animal_species,
            competency_slugs=frozenset(s.strip().lower() for s in params.competency_slugs if s.strip()),
            keywords=frozenset(k.strip().lower() for k in params.keywords if k.strip()),
        )
        candidates = self.repo.list_context_tip_candidates()
        picked = pick_hints(candidates, ctx, limit=params.limit)
        items = [
            KnowledgeHintItem(
                id=row.article.id,
                title=row.article.title,
                summary=row.article.summary,
                cover_url=self._cover_url(row.article.cover_path),
                category=row.article.category,
                category_label=_CATEGORY_LABELS.get(row.article.category),
                read_minutes=row.article.read_minutes,
                match_score=row.score,
                match_reasons=list(row.reasons),
            )
            for row in picked
        ]
        return KnowledgeHintsResponse(total=len(items), items=items)

    def _to_detail(self, row: KnowledgeArticle, viewer: User | None = None) -> KnowledgeDetail:
        return KnowledgeDetail(
            id=row.id,
            title=row.title,
            summary=row.summary,
            cover_url=self._cover_url(row.cover_path),
            content=row.content,
            category=row.category,
            category_label=_CATEGORY_LABELS.get(row.category),
            read_minutes=row.read_minutes,
            is_context_tip=bool(row.is_context_tip),
            owner_role=row.owner_role,
            author_user_id=row.author_user_id,
            can_edit=self.can_edit_article(row, viewer),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create_article(self, user: User, payload: KnowledgeUpsertRequest) -> KnowledgeDetail:
        self._ensure_writer(user)
        art = KnowledgeArticle(
            author_user_id=user.id,
            owner_role=self._user_role_value(user),
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
        if art.is_published:
            invalidate_knowledge_article(int(art.id))
        return self.get_detail(art.id, user)

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
        invalidate_knowledge_article(article_id)
        return self.get_detail(art.id, user)

    def delete_article(self, article_id: int, user: User) -> None:
        self._ensure_writer(user)
        art = self.repo.get_article_for_owner(article_id)
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        self._ensure_can_edit(art, user)
        self.repo.db.delete(art)
        self.repo.db.commit()
        invalidate_knowledge_article(article_id)

    def upload_cover(self, article_id: int, user: User, file: UploadFile) -> KnowledgeDetail:
        self._ensure_writer(user)
        art = self.repo.get_article_for_owner(article_id)
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        self._ensure_can_edit(art, user)
        try:
            art.cover_path = save_knowledge_cover(settings.media_dir, int(art.id), file)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        self.repo.db.commit()
        invalidate_knowledge_article(article_id)
        return self.get_detail(art.id, user)

    def archive_article(self, article_id: int, user: User) -> KnowledgeDetail:
        self._ensure_writer(user)
        art = self.repo.get_article_for_owner(article_id)
        if not art:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        self._ensure_can_edit(art, user)
        art.is_archived = True
        self.repo.db.commit()
        invalidate_knowledge_article(article_id)
        return self.get_detail(art.id, user)

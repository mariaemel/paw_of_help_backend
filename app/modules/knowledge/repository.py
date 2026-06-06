from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.core.list_query import apply_text_search
from app.models.knowledge import KnowledgeArticle
from app.modules.knowledge.schemas import KnowledgeFilterParams


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def _list_articles_query(self, filters: KnowledgeFilterParams):
        q = self.db.query(KnowledgeArticle).filter(
            KnowledgeArticle.is_archived.is_(False),
            KnowledgeArticle.is_published.is_(True),
        )
        q = apply_text_search(q, filters.q, KnowledgeArticle.title, KnowledgeArticle.summary)
        if filters.category and filters.category != "all":
            q = q.filter(KnowledgeArticle.category == filters.category)
        if filters.only_context_tips is True:
            q = q.filter(KnowledgeArticle.is_context_tip.is_(True))
        return q

    def list_articles(self, filters: KnowledgeFilterParams) -> tuple[int, list[KnowledgeArticle]]:
        q = self._list_articles_query(filters)
        total = q.order_by(None).count()

        if filters.sort_by == "title":
            q = q.order_by(asc(KnowledgeArticle.title), asc(KnowledgeArticle.id))
        elif filters.sort_by == "read_minutes":
            q = q.order_by(asc(KnowledgeArticle.read_minutes), asc(KnowledgeArticle.id))
        else:
            q = q.order_by(desc(KnowledgeArticle.created_at), desc(KnowledgeArticle.id))

        rows = q.offset(filters.offset).limit(filters.limit).all()
        return total, rows

    def get_article(self, article_id: int) -> KnowledgeArticle | None:
        return (
            self.db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.id == article_id,
                KnowledgeArticle.is_archived.is_(False),
                KnowledgeArticle.is_published.is_(True),
            )
            .first()
        )

    def get_article_for_owner(self, article_id: int) -> KnowledgeArticle | None:
        return self.db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()

    def list_my_articles(
        self, author_user_id: int, owner_role: str, limit: int, offset: int, tab: str = "all"
    ) -> tuple[int, list[KnowledgeArticle]]:
        owner_role_norm = owner_role.strip().lower()
        q = self.db.query(KnowledgeArticle).filter(
            KnowledgeArticle.author_user_id == author_user_id,
            func.lower(KnowledgeArticle.owner_role) == owner_role_norm,
        )
        if tab == "archive":
            q = q.filter(KnowledgeArticle.is_archived.is_(True))
        elif tab == "active":
            q = q.filter(KnowledgeArticle.is_archived.is_(False))
        total = int(q.order_by(None).count() or 0)
        rows = (
            q.order_by(KnowledgeArticle.created_at.desc(), KnowledgeArticle.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, rows

    def list_context_tip_candidates(self) -> list[KnowledgeArticle]:
        return (
            self.db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.is_context_tip.is_(True),
                KnowledgeArticle.is_archived.is_(False),
                KnowledgeArticle.is_published.is_(True),
            )
            .order_by(KnowledgeArticle.created_at.desc(), KnowledgeArticle.id.desc())
            .limit(500)
            .all()
        )

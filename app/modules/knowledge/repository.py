from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeArticle
from app.modules.knowledge.schemas import KnowledgeFilterParams


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_articles(self, filters: KnowledgeFilterParams) -> tuple[int, list[KnowledgeArticle]]:
        q = self.db.query(KnowledgeArticle).filter(
            KnowledgeArticle.is_archived.is_(False),
            KnowledgeArticle.is_published.is_(True),
        )
        if filters.q:
            like = f"%{filters.q.lower()}%"
            q = q.filter(
                (func.lower(KnowledgeArticle.title).like(like))
                | (func.lower(KnowledgeArticle.summary).like(like))
                | (func.lower(KnowledgeArticle.content).like(like))
            )
        if filters.category and filters.category != "all":
            q = q.filter(KnowledgeArticle.category == filters.category)
        if filters.only_context_tips is True:
            q = q.filter(KnowledgeArticle.is_context_tip.is_(True))

        rows = q.all()
        if filters.sort_by == "title":
            rows.sort(key=lambda x: (x.title.lower(), x.id))
        elif filters.sort_by == "read_minutes":
            rows.sort(key=lambda x: (x.read_minutes, x.id))
        else:
            rows.sort(key=lambda x: (x.created_at, x.id), reverse=True)
        total = len(rows)
        return total, rows[filters.offset : filters.offset + filters.limit]

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

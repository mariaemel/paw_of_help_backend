from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.knowledge import KnowledgeArticle

MIN_HINT_SCORE = 8.0

_HELP_TYPE_CATEGORIES: dict[str, frozenset[str]] = {
    "medical": frozenset({"treatment", "first_aid", "care"}),
    "foster": frozenset({"care", "adaptation", "socialization"}),
    "manual": frozenset({"care", "training", "socialization"}),
    "auto": frozenset({"care", "legal"}),
    "food": frozenset({"care"}),
    "financial": frozenset({"legal", "care"}),
}

_SPECIES_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cat": ("кош", "кот", "кошк", "котён", "котен"),
    "dog": ("собак", "пёс", "пес", "щен"),
    "other": ("грызун", "птиц", "кролик", "хомяк"),
}

_COMPETENCY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "foster": ("передерж", "уход", "содержан"),
    "transport": ("перевоз", "транспорт", "авто"),
    "medical": ("лечен", "медиц", "ветерин", "укол", "таблет"),
    "manual": ("убор", "корм", "выгул", "руками"),
    "auto": ("авто", "перевоз", "достав"),
    "food": ("корм", "кормлен"),
    "financial": ("сбор", "оплат", "перевод"),
}


@dataclass(frozen=True)
class HintContext:
    help_type: str | None = None
    animal_species: str | None = None
    competency_slugs: frozenset[str] = frozenset()
    keywords: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ScoredHint:
    article: KnowledgeArticle
    score: float
    reasons: tuple[str, ...]


def _article_json_list(raw: str | None) -> set[str]:
    if not raw:
        return set()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return set()
    if not isinstance(data, list):
        return set()
    return {str(x).strip().lower() for x in data if str(x).strip()}


def _blob(article: KnowledgeArticle) -> str:
    return f"{article.title}\n{article.summary or ''}\n{article.content}".lower()


def score_hint(article: KnowledgeArticle, ctx: HintContext) -> ScoredHint | None:
    if not article.is_context_tip or article.is_archived or not article.is_published:
        return None

    reasons: list[str] = []
    score = 0.0

    help_type = (ctx.help_type or "").strip().lower()
    species = (ctx.animal_species or "").strip().lower()
    blob = _blob(article)

    target_types = _article_json_list(getattr(article, "target_help_types_json", None))
    target_species = _article_json_list(getattr(article, "target_species_json", None))
    target_comps = _article_json_list(getattr(article, "target_competency_slugs_json", None))
    article_keywords = _article_json_list(getattr(article, "keywords_json", None))

    if target_types:
        if help_type and help_type in target_types:
            score += 28.0
            reasons.append("help_type")
        elif help_type:
            return None
    elif help_type:
        cats = _HELP_TYPE_CATEGORIES.get(help_type, frozenset())
        if article.category in cats:
            score += 18.0
            reasons.append("category")

    if target_species:
        if species and species in target_species:
            score += 22.0
            reasons.append("species")
        elif species:
            return None
    elif species:
        for kw in _SPECIES_KEYWORDS.get(species, ()):
            if kw in blob:
                score += 14.0
                reasons.append("species")
                break

    overlap = ctx.competency_slugs & (target_comps or ctx.competency_slugs)
    if target_comps:
        if overlap:
            score += 20.0 * (len(overlap) / max(len(target_comps), 1))
            reasons.append("competencies")
        elif ctx.competency_slugs:
            return None
    elif ctx.competency_slugs:
        for slug in ctx.competency_slugs:
            for kw in _COMPETENCY_KEYWORDS.get(slug, ()):
                if kw in blob:
                    score += 10.0
                    reasons.append("competencies")
                    break

    keyword_hits = 0
    for kw in ctx.keywords | article_keywords:
        token = kw.strip().lower()
        if len(token) < 3:
            continue
        if token in blob:
            keyword_hits += 1
    if keyword_hits:
        score += min(16.0, 6.0 * keyword_hits)
        reasons.append("keywords")

    if score < MIN_HINT_SCORE:
        return None

    return ScoredHint(article=article, score=round(score, 1), reasons=tuple(dict.fromkeys(reasons)))


def pick_hints(articles: list[KnowledgeArticle], ctx: HintContext, *, limit: int = 3) -> list[ScoredHint]:
    scored: list[ScoredHint] = []
    for article in articles:
        item = score_hint(article, ctx)
        if item is not None:
            scored.append(item)
    scored.sort(key=lambda x: (-x.score, -x.article.created_at.timestamp(), -x.article.id))
    return scored[:limit]

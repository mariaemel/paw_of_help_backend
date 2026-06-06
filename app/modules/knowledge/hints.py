from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.models.knowledge import KnowledgeArticle

MIN_HINT_SCORE = 12.0
_STRONG_REASONS = frozenset({"help_type", "species", "competencies", "keywords"})

_HELP_TYPE_CATEGORIES: dict[str, frozenset[str]] = {
    "medical": frozenset({"treatment", "first_aid", "care"}),
    "foster": frozenset({"care", "adaptation", "socialization"}),
    "manual": frozenset({"care", "training", "socialization"}),
    "auto": frozenset({"care", "first_aid", "legal"}),
    "photo_video": frozenset({"training", "care", "socialization"}),
    "food": frozenset({"care"}),
    "financial": frozenset({"legal", "care"}),
}

_MEDICAL_CATEGORIES = frozenset({"first_aid", "treatment"})
_PHOTO_CATEGORIES = frozenset({"training", "care"})

_SPECIES_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cat": ("кош", "кот", "кошк", "котён", "котен", "котят"),
    "dog": ("собак", "пёс", "пес", "щен", "псов"),
    "other": ("грызун", "птиц", "кролик", "хомяк"),
}

_COMPETENCY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "foster": ("передерж", "уход", "содержан"),
    "walk": ("выгул", "прогул", "гуля"),
    "photo_video": ("фотос", "фотограф", "съём", "съем", "видеос", "кадр", "сним"),
    "manual": ("убор", "корм", "приют", "вольер", "руками"),
    "auto": ("авто", "перевоз", "транспорт", "достав", "водител", "машин"),
    "medical": ("лечен", "медиц", "ветерин", "укол", "таблет", "клиник", "рентген", "отрав"),
    "food": ("корм", "кормлен"),
    "financial": ("сбор", "оплат", "перевод"),
}

_TASK_TOPIC_PATTERNS: tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...] = (
    (re.compile(r"перевоз|транспорт|авто|довез|подвез|водител", re.I), ("перевоз", "авто", "транспорт"), "transport"),
    (re.compile(r"клиник|ветерин|рентген|лечен|операц|отрав|болезн|медиц", re.I), ("клиник", "ветерин", "лечение"), "medical"),
    (re.compile(r"выгул|прогул|гуля", re.I), ("выгул", "прогулка"), "walk"),
    (re.compile(r"передерж", re.I), ("передержка", "передерж"), "foster"),
    (re.compile(r"убор|вольер|приют", re.I), ("приют", "уборка"), "shelter"),
    (re.compile(r"фото|видео|съ[её]м|сним|камер|фотос", re.I), ("фото", "видео", "съемка", "фотосъемка"), "photo"),
    (re.compile(r"порез|рана|травм|первая помощ", re.I), ("рана", "первая помощь"), "medical"),
)

_TOPIC_BY_HELP_TYPE: dict[str, str] = {
    "auto": "transport",
    "medical": "medical",
    "photo_video": "photo",
    "foster": "foster",
    "manual": "shelter",
    "walk": "walk",
}

_INCOMPATIBLE_TOPICS: dict[str, frozenset[str]] = {
    "photo": frozenset({"medical"}),
    "transport": frozenset({"medical"}),
    "walk": frozenset({"medical"}),
    "foster": frozenset(),
    "shelter": frozenset({"medical"}),
    "medical": frozenset({"photo"}),
}


@dataclass(frozen=True)
class HintContext:
    help_type: str | None = None
    animal_species: str | None = None
    competency_slugs: frozenset[str] = frozenset()
    keywords: frozenset[str] = frozenset()
    task_text: str | None = None


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


def _head_blob(article: KnowledgeArticle) -> str:
    keywords = " ".join(sorted(_article_json_list(getattr(article, "keywords_json", None))))
    return f"{article.title}\n{article.summary or ''}\n{keywords}".lower()


def _detect_species_in_text(text: str) -> frozenset[str]:
    low = text.lower()
    found: set[str] = set()
    for species, tokens in _SPECIES_KEYWORDS.items():
        if any(token in low for token in tokens):
            found.add(species)
    return frozenset(found)


def _resolve_task_species(ctx: HintContext) -> str | None:
    explicit = (ctx.animal_species or "").strip().lower()
    if explicit in _SPECIES_KEYWORDS:
        return explicit

    text = "\n".join(
        part.strip()
        for part in (ctx.task_text or "", " ".join(sorted(ctx.keywords)))
        if part and part.strip()
    )
    detected = _detect_species_in_text(text)
    if len(detected) == 1:
        return next(iter(detected))
    return None


def _article_species_profile(article: KnowledgeArticle) -> frozenset[str]:
    target = _article_json_list(getattr(article, "target_species_json", None))
    if target:
        return frozenset(target)
    return _detect_species_in_text(f"{article.title}\n{article.summary or ''}")


def _species_conflict(task_species: str | None, article_species: frozenset[str]) -> bool:
    if not task_species or not article_species:
        return False
    return task_species not in article_species


def infer_task_topics(*, task_text: str | None, help_type: str | None) -> frozenset[str]:
    topics: set[str] = set()
    text = (task_text or "").strip()
    ht = (help_type or "").strip().lower()
    if ht in _TOPIC_BY_HELP_TYPE:
        topics.add(_TOPIC_BY_HELP_TYPE[ht])
    for pattern, _tokens, topic in _TASK_TOPIC_PATTERNS:
        if text and pattern.search(text):
            topics.add(topic)
    return frozenset(topics)


def _infer_article_topics(article: KnowledgeArticle) -> frozenset[str]:
    topics: set[str] = set()
    target_types = _article_json_list(getattr(article, "target_help_types_json", None))
    for ht in target_types:
        mapped = _TOPIC_BY_HELP_TYPE.get(ht)
        if mapped:
            topics.add(mapped)

    head = _head_blob(article)
    for pattern, _tokens, topic in _TASK_TOPIC_PATTERNS:
        if pattern.search(head):
            topics.add(topic)

    if article.category in _MEDICAL_CATEGORIES:
        topics.add("medical")
    if article.category in _PHOTO_CATEGORIES and re.search(r"фото|видео|съ[её]м", head, re.I):
        topics.add("photo")

    return frozenset(topics)


def _topics_compatible(task_topics: frozenset[str], article_topics: frozenset[str]) -> bool:
    if not task_topics or not article_topics:
        return True

    if task_topics & article_topics:
        return True

    for task_topic in task_topics:
        incompatible = _INCOMPATIBLE_TOPICS.get(task_topic, frozenset())
        if article_topics & incompatible:
            return False

    if "photo" in task_topics and article_topics <= {"medical"}:
        return False
    if "medical" in task_topics and article_topics <= {"photo"}:
        return False

    return not task_topics or not article_topics


def _category_fallback_score(help_type: str, category: str) -> float:
    cats = _HELP_TYPE_CATEGORIES.get(help_type, frozenset())
    if category in cats:
        return 8.0
    return 0.0


def _count_keyword_hits(task_keywords: set[str], article_head: str) -> int:
    hits = 0
    for kw in task_keywords:
        token = kw.strip().lower()
        if len(token) < 3:
            continue
        if token in article_head:
            hits += 1
    return hits


def score_hint(article: KnowledgeArticle, ctx: HintContext) -> ScoredHint | None:
    if not article.is_context_tip or article.is_archived or not article.is_published:
        return None

    task_topics = infer_task_topics(task_text=ctx.task_text, help_type=ctx.help_type)
    article_topics = _infer_article_topics(article)
    if not _topics_compatible(task_topics, article_topics):
        return None

    reasons: list[str] = []
    score = 0.0

    help_type = (ctx.help_type or "").strip().lower()
    species = _resolve_task_species(ctx)
    head = _head_blob(article)
    article_species = _article_species_profile(article)

    if _species_conflict(species, article_species):
        return None

    target_types = _article_json_list(getattr(article, "target_help_types_json", None))
    target_species = _article_json_list(getattr(article, "target_species_json", None))
    target_comps = _article_json_list(getattr(article, "target_competency_slugs_json", None))
    article_keywords = _article_json_list(getattr(article, "keywords_json", None))

    if target_types:
        if help_type and help_type in target_types:
            score += 30.0
            reasons.append("help_type")
        elif help_type:
            return None
    elif help_type:
        category_score = _category_fallback_score(help_type, article.category)
        if category_score > 0 and _topics_compatible(task_topics, article_topics):
            score += category_score
            reasons.append("category")

    if target_species:
        if species and species in target_species:
            score += 24.0
            reasons.append("species")
        elif species:
            return None
    elif species:
        if species in article_species:
            score += 18.0
            reasons.append("species")
        else:
            for kw in _SPECIES_KEYWORDS.get(species, ()):
                if kw in head:
                    score += 14.0
                    reasons.append("species")
                    break

    if target_comps:
        overlap = ctx.competency_slugs & target_comps
        if overlap:
            score += 22.0 * (len(overlap) / max(len(target_comps), 1))
            reasons.append("competencies")
        elif ctx.competency_slugs:
            return None
    elif ctx.competency_slugs:
        matched = False
        for slug in ctx.competency_slugs:
            for kw in _COMPETENCY_KEYWORDS.get(slug, ()):
                if kw in head:
                    score += 12.0
                    reasons.append("competencies")
                    matched = True
                    break
            if matched:
                break

    task_keywords = set(ctx.keywords) | set(article_keywords)
    keyword_hits = _count_keyword_hits(task_keywords, head)
    if keyword_hits:
        score += min(18.0, 7.0 * keyword_hits)
        reasons.append("keywords")

    unique_reasons = tuple(dict.fromkeys(reasons))
    has_strong_reason = any(reason in _STRONG_REASONS for reason in unique_reasons)
    if not has_strong_reason:
        return None

    if score < MIN_HINT_SCORE:
        return None

    return ScoredHint(article=article, score=round(score, 1), reasons=unique_reasons)


def pick_hints(articles: list[KnowledgeArticle], ctx: HintContext, *, limit: int = 3) -> list[ScoredHint]:
    scored: list[ScoredHint] = []
    for article in articles:
        item = score_hint(article, ctx)
        if item is not None:
            scored.append(item)
    scored.sort(key=lambda x: (-x.score, -x.article.created_at.timestamp(), -x.article.id))
    return scored[:limit]


def build_help_request_knowledge_hints(
    req,
    *,
    required_competencies: frozenset[str] | set[str] | tuple[str, ...] | list[str],
    articles: list[KnowledgeArticle],
    limit: int = 2,
) -> list[ScoredHint]:
    parts = [
        (getattr(req, "title", None) or "").strip(),
        (getattr(req, "description", None) or "").strip(),
        (getattr(req, "volunteer_requirements", None) or "").strip(),
    ]
    task_text = "\n".join(part for part in parts if part)
    help_type = (getattr(req, "help_type", None) or "").strip().lower() or None
    animal = getattr(req, "animal", None)
    species = None
    if animal is not None and getattr(animal, "species", None):
        species = str(animal.species).strip().lower() or None

    keywords = extract_task_keywords(task_text, help_type=help_type) if task_text else []
    ctx = HintContext(
        help_type=help_type,
        animal_species=species,
        competency_slugs=frozenset(str(x).strip().lower() for x in required_competencies if str(x).strip()),
        keywords=frozenset(keywords),
        task_text=task_text or None,
    )
    return pick_hints(articles, ctx, limit=limit)


def extract_task_keywords(task_text: str, *, help_type: str | None = None) -> list[str]:
    text = task_text.strip()
    if not text:
        return []

    keywords: set[str] = set()
    for pattern, tokens, _topic in _TASK_TOPIC_PATTERNS:
        if pattern.search(text):
            keywords.update(tokens)

    ht = (help_type or "").strip().lower()
    if ht:
        keywords.add(ht)
        for kw in _COMPETENCY_KEYWORDS.get(ht, ()):
            keywords.add(kw)

    for species, tokens in _SPECIES_KEYWORDS.items():
        if any(token in text.lower() for token in tokens):
            keywords.add(species)

    return sorted(keywords)

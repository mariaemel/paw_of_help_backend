from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.animal import Animal
from app.modules.animals.catalog_constants import (
    FEATURE_ID_HEALTH_NOTES,
    FEATURE_ID_URGENT,
    LABEL_HEALTH_NOTES,
    LABEL_URGENT,
)
from app.modules.animals.schemas import FeatureFilterOption

if TYPE_CHECKING:
    from app.modules.animals.repository import AnimalRepository


def animal_has_health_issue_notes(animal: Animal) -> bool:
    for raw in (animal.health_features, animal.treatment_required):
        if raw is not None and str(raw).strip():
            return True
    return False


def labels_for_catalog_kind(animal: Animal, kind: str) -> list[str]:
    rows: list[tuple[int, str]] = []
    for asg in animal.catalog_assignments or []:
        ci = asg.catalog_item
        if ci is None or ci.kind != kind:
            continue
        rows.append((ci.sort_order, ci.label))
    rows.sort(key=lambda x: (x[0], x[1]))
    return [r[1] for r in rows]


def combined_catalog_feature_labels(animal: Animal) -> list[str]:
    out: list[str] = []
    if animal.is_urgent:
        out.append(LABEL_URGENT)
    out.extend(labels_for_catalog_kind(animal, "health_care"))
    out.extend(labels_for_catalog_kind(animal, "character"))
    if animal_has_health_issue_notes(animal):
        out.append(LABEL_HEALTH_NOTES)
    return out


def build_catalog_feature_filter_options(repo: AnimalRepository) -> list[FeatureFilterOption]:
    out: list[FeatureFilterOption] = [
        FeatureFilterOption(id=FEATURE_ID_URGENT, label=LABEL_URGENT),
    ]
    for slug, label in repo.list_catalog_options("health_care"):
        out.append(FeatureFilterOption(id=f"health_care/{slug}", label=label))
    for slug, label in repo.list_catalog_options("character"):
        out.append(FeatureFilterOption(id=f"character/{slug}", label=label))
    out.append(FeatureFilterOption(id=FEATURE_ID_HEALTH_NOTES, label=LABEL_HEALTH_NOTES))
    return out

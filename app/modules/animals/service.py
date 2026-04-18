from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.animals.constants import AGE_GROUPS, FEATURE_FILTERS, SPECIES_LABELS
from app.modules.animals.jsonutil import parse_json_list
from app.modules.animals.repository import AnimalRepository
from app.modules.animals.schemas import (
    AgeGroupOption,
    AnimalCatalogsResponse,
    AnimalDetail,
    AnimalFilterParams,
    AnimalListResponse,
    FeatureFilterOption,
    OrganizationBrief,
    OrganizationOption,
)
from app.modules.animals.storage import save_animal_image
from app.modules.animals.tags import build_card_tags


class AnimalService:
    def __init__(self, repo: AnimalRepository):
        self.repo = repo

    def _item_dict(self, animal) -> dict:
        primary_photo = next((p for p in animal.photos if p.is_primary), None)
        if not primary_photo and animal.photos:
            primary_photo = animal.photos[0]
        primary_photo_url = (
            f"{settings.media_url_prefix}/{primary_photo.file_path}" if primary_photo else None
        )
        species = getattr(animal, "species", None) or "cat"
        breed = getattr(animal, "breed", None)
        age_m = getattr(animal, "age_months", 0) or 0
        org_name = animal.organization.name if animal.organization else None
        oid = animal.organization_id
        return {
            "id": animal.id,
            "name": animal.name,
            "species": species,
            "sex": animal.sex,
            "age_months": age_m,
            "location_city": animal.location_city,
            "is_urgent": animal.is_urgent,
            "status": animal.status,
            "short_story": animal.short_story,
            "primary_photo_url": primary_photo_url,
            "breed": breed,
            "card_tags": build_card_tags(species, breed, age_m),
            "organization_id": oid,
            "organization_name": org_name,
        }

    def get_catalog(self, filters: AnimalFilterParams) -> AnimalListResponse:
        total, items = self.repo.list_animals(filters)
        response_items = [self._item_dict(a) for a in items]
        return AnimalListResponse(total=total, items=response_items)

    def get_filters_catalogs(self) -> AnimalCatalogsResponse:
        statuses, sexes, cities = self.repo.get_catalogs()
        org_opts = self.repo.list_organization_options()
        age_groups = [AgeGroupOption(**g) for g in AGE_GROUPS]
        features = [FeatureFilterOption(id=f["id"], label=f["label"]) for f in FEATURE_FILTERS]
        return AnimalCatalogsResponse(
            statuses=statuses,
            sexes=sexes,
            cities=cities,
            urgent_options=[True, False],
            species=list(SPECIES_LABELS.keys()),
            age_groups=age_groups,
            features=features,
            organizations=[OrganizationOption(id=o[0], name=o[1]) for o in org_opts],
        )

    def get_card(self, animal_id: int) -> AnimalDetail:
        animal = self.repo.get_by_id(animal_id)
        if not animal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

        primary_photo = next((p for p in animal.photos if p.is_primary), None)
        if not primary_photo and animal.photos:
            primary_photo = animal.photos[0]
        photo_urls = [f"{settings.media_url_prefix}/{p.file_path}" for p in animal.photos]
        species = getattr(animal, "species", None) or "cat"
        breed = getattr(animal, "breed", None)
        age_m = getattr(animal, "age_months", 0) or 0

        org_brief = None
        if animal.organization:
            org_brief = OrganizationBrief(
                id=animal.organization.id,
                name=animal.organization.name,
                city=animal.organization.city,
            )

        checklist = parse_json_list(getattr(animal, "health_checklist_json", None))
        char_tags = parse_json_list(getattr(animal, "character_tags_json", None))
        full_desc = getattr(animal, "full_description", None) or animal.short_story

        return AnimalDetail(
            id=animal.id,
            name=animal.name,
            species=species,
            breed=breed,
            sex=animal.sex,
            age_months=age_m,
            location_city=animal.location_city,
            is_urgent=animal.is_urgent,
            status=animal.status,
            short_story=animal.short_story,
            full_description=full_desc,
            primary_photo_url=(
                f"{settings.media_url_prefix}/{primary_photo.file_path}" if primary_photo else None
            ),
            photo_urls=photo_urls,
            card_tags=build_card_tags(species, breed, age_m),
            organization=org_brief,
            health_checklist=checklist,
            health_features=getattr(animal, "health_features", None),
            treatment_required=getattr(animal, "treatment_required", None),
            health_info=animal.health_info,
            character_tags=char_tags,
            character_info=animal.character_info,
            help_options=animal.help_options,
            urgent_needs_text=getattr(animal, "urgent_needs_text", None),
            latitude=animal.latitude,
            longitude=animal.longitude,
            created_at=animal.created_at,
        )

    def upload_image(self, animal_id: int, file, is_primary: bool) -> dict:
        animal = self.repo.get_by_id(animal_id)
        if not animal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")
        try:
            file_path = save_animal_image(settings.media_dir, animal_id, file)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        photo = self.repo.add_photo(animal_id=animal_id, file_path=file_path, is_primary=is_primary)
        return {
            "id": photo.id,
            "animal_id": photo.animal_id,
            "is_primary": photo.is_primary,
            "url": f"{settings.media_url_prefix}/{photo.file_path}",
        }

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.modules.animals.catalog_marks import (
    build_catalog_feature_filter_options,
    combined_catalog_feature_labels,
    labels_for_catalog_kind,
)
from app.modules.animals.display_catalog import AGE_GROUPS, SPECIES_LABELS
from app.modules.animals.repository import AnimalRepository
from app.modules.animals.schemas import (
    AgeGroupOption,
    AnimalCatalogsResponse,
    AnimalDetail,
    AnimalFilterParams,
    AnimalListResponse,
    AnimalLinkedRequestShort,
    CatalogTagOption,
    FeatureFilterOption,
    OrganizationBrief,
    OrganizationOption,
)
from app.modules.animals.storage import save_animal_image
from app.modules.animals.tags import species_label_ru


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
            "species": species_label_ru(species, animal.sex),
            "sex": animal.sex,
            "age_months": age_m,
            "location_city": animal.location_city,
            "is_urgent": animal.is_urgent,
            "status": animal.status,
            "full_description": getattr(animal, "full_description", None),
            "primary_photo_url": primary_photo_url,
            "breed": breed,
            "organization_id": oid,
            "organization_name": org_name,
            "catalog_features": combined_catalog_feature_labels(animal),
        }

    def get_catalog(self, filters: AnimalFilterParams) -> AnimalListResponse:
        total, items = self.repo.list_animals(filters)
        response_items = [self._item_dict(a) for a in items]
        return AnimalListResponse(total=total, items=response_items)

    def get_filters_catalogs(self) -> AnimalCatalogsResponse:
        statuses, sexes, cities = self.repo.get_catalogs()
        org_opts = self.repo.list_organization_options()
        age_groups = [AgeGroupOption(**g) for g in AGE_GROUPS]
        features = build_catalog_feature_filter_options(self.repo)
        health_rows = self.repo.list_catalog_options("health_care")
        character_rows = self.repo.list_catalog_options("character")
        return AnimalCatalogsResponse(
            statuses=statuses,
            sexes=sexes,
            cities=cities,
            urgent_options=[True, False],
            species=list(SPECIES_LABELS.keys()),
            age_groups=age_groups,
            features=features,
            health_care_tags=[CatalogTagOption(id=s, label=l) for s, l in health_rows],
            character_tags=[CatalogTagOption(id=s, label=l) for s, l in character_rows],
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

        full_desc = getattr(animal, "full_description", None)
        checklist = labels_for_catalog_kind(animal, "health_care")
        char_tags = labels_for_catalog_kind(animal, "character")

        return AnimalDetail(
            id=animal.id,
            name=animal.name,
            species=species_label_ru(species, animal.sex),
            breed=breed,
            sex=animal.sex,
            age_months=age_m,
            location_city=animal.location_city,
            is_urgent=animal.is_urgent,
            status=animal.status,
            full_description=full_desc,
            primary_photo_url=(
                f"{settings.media_url_prefix}/{primary_photo.file_path}" if primary_photo else None
            ),
            photo_urls=photo_urls,
            organization=org_brief,
            health_checklist=checklist,
            health_features=getattr(animal, "health_features", None),
            treatment_required=getattr(animal, "treatment_required", None),
            character_tags=char_tags,
            help_options=animal.help_options,
            urgent_needs_text=getattr(animal, "urgent_needs_text", None),
            linked_help_requests=[
                AnimalLinkedRequestShort(
                    id=r.id,
                    title=r.title,
                    status=r.status,
                    is_urgent=bool(r.is_urgent),
                    help_type=r.help_type,
                    volunteer_needed=bool(r.volunteer_needed),
                    deadline_at=r.deadline_at,
                )
                for r in (animal.help_requests or [])
                if not r.is_archived and r.is_published
            ],
            created_at=animal.created_at,
        )

    def upload_image(self, animal_id: int, file, is_primary: bool, user: User) -> dict:
        if user.role != UserRole.ORGANIZATION:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization role required")
        org = (
            self.repo.db.query(Organization)
            .filter(Organization.owner_user_id == user.id)
            .order_by(Organization.id.asc())
            .first()
        )
        if org is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization profile not found")
        animal = self.repo.get_by_id(animal_id)
        if not animal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")
        if animal.organization_id != org.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only upload images for animals owned by your organization",
            )
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

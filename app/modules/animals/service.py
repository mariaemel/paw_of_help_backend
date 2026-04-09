from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.animals.repository import AnimalRepository
from app.modules.animals.schemas import (
    AnimalCatalogsResponse,
    AnimalDetail,
    AnimalFilterParams,
    AnimalListResponse,
)
from app.modules.animals.storage import save_animal_image


class AnimalService:
    def __init__(self, repo: AnimalRepository):
        self.repo = repo

    def get_catalog(self, filters: AnimalFilterParams) -> AnimalListResponse:
        total, items = self.repo.list_animals(filters)
        response_items = []
        for animal in items:
            primary_photo = next((p for p in animal.photos if p.is_primary), None)
            if not primary_photo and animal.photos:
                primary_photo = animal.photos[0]
            primary_photo_url = (
                f"{settings.media_url_prefix}/{primary_photo.file_path}" if primary_photo else None
            )
            response_items.append(
                {
                    "id": animal.id,
                    "name": animal.name,
                    "sex": animal.sex,
                    "age_months": animal.age_months,
                    "location_city": animal.location_city,
                    "is_urgent": animal.is_urgent,
                    "status": animal.status,
                    "short_story": animal.short_story,
                    "primary_photo_url": primary_photo_url,
                }
            )
        return AnimalListResponse(total=total, items=response_items)

    def get_filters_catalogs(self) -> AnimalCatalogsResponse:
        statuses, sexes, cities = self.repo.get_catalogs()
        return AnimalCatalogsResponse(
            statuses=statuses, sexes=sexes, cities=cities, urgent_options=[True, False]
        )

    def get_card(self, animal_id: int) -> AnimalDetail:
        animal = self.repo.get_by_id(animal_id)
        if not animal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")
        primary_photo = next((p for p in animal.photos if p.is_primary), None)
        if not primary_photo and animal.photos:
            primary_photo = animal.photos[0]
        photo_urls = [f"{settings.media_url_prefix}/{p.file_path}" for p in animal.photos]
        return AnimalDetail.model_validate(
            {
                "id": animal.id,
                "name": animal.name,
                "sex": animal.sex,
                "age_months": animal.age_months,
                "location_city": animal.location_city,
                "is_urgent": animal.is_urgent,
                "status": animal.status,
                "short_story": animal.short_story,
                "health_info": animal.health_info,
                "character_info": animal.character_info,
                "help_options": animal.help_options,
                "latitude": animal.latitude,
                "longitude": animal.longitude,
                "created_at": animal.created_at,
                "primary_photo_url": (
                    f"{settings.media_url_prefix}/{primary_photo.file_path}" if primary_photo else None
                ),
                "photo_urls": photo_urls,
            }
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

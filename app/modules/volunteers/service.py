from app.modules.volunteers.repository import VolunteerRepository
from app.modules.volunteers.schemas import (
    VolunteerCatalogsResponse,
    VolunteerFilterParams,
    VolunteerListItem,
    VolunteerListResponse,
)


class VolunteerService:
    def __init__(self, repo: VolunteerRepository):
        self.repo = repo

    def list_volunteers(self, filters: VolunteerFilterParams) -> VolunteerListResponse:
        total, rows = self.repo.list_volunteers(filters)
        items = [
            VolunteerListItem(
                user_id=user.id,
                full_name=user.full_name,
                location_city=profile.location_city,
                skills=profile.skills,
                experience=profile.experience,
                availability=profile.availability,
                travel_radius_km=profile.travel_radius_km,
                preferred_help_format=profile.preferred_help_format,
                animal_categories=profile.animal_categories,
            )
            for user, profile in rows
        ]
        return VolunteerListResponse(total=total, items=items)

    def get_catalogs(self) -> VolunteerCatalogsResponse:
        return VolunteerCatalogsResponse(cities=self.repo.list_catalogs())

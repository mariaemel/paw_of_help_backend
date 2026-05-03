from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.help.repository import HelpRepository
from app.modules.help.schemas import HelpListResponse
from app.modules.help.service import HelpService


router = APIRouter(prefix="/help", tags=["help"])


def get_help_service(db: Session = Depends(get_db)) -> HelpService:
    return HelpService(HelpRepository(db))


@router.get("/animals", response_model=HelpListResponse)
def list_help_animals(
    tab: str = Query(default="all", description="Фильтр: all | adopt | feed | heal | other"),
    service: HelpService = Depends(get_help_service),
):
    return service.list_cards(tab)

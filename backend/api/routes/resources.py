from fastapi import APIRouter, Depends

from backend.api.dependencies import get_current_session
from backend.resources_catalog import RESOURCES


router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
def list_resources(session=Depends(get_current_session)):
    return {"categories": RESOURCES}

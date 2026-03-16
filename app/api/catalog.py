from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_account
from app.catalog import SERVICE_CATALOG
from app.models import Account

router = APIRouter(prefix="/v1", tags=["catalog"])


@router.get("/services")
def list_services(_: Annotated[Account, Depends(get_current_account)]) -> dict[str, list[dict[str, Any]]]:
    return {"services": SERVICE_CATALOG}

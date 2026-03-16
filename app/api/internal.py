from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.schemas import DepositConfirmRequest, DepositConfirmResponse
from app.services.deposits import apply_confirmed_deposit

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/deposits/confirm", response_model=DepositConfirmResponse, status_code=status.HTTP_202_ACCEPTED)
def confirm_deposit_route(
    payload: DepositConfirmRequest,
    session: Annotated[Session, Depends(get_session)],
) -> DepositConfirmResponse:
    status_value = apply_confirmed_deposit(session, **payload.model_dump())
    return DepositConfirmResponse(status=status_value)

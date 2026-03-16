from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_account, get_session
from app.models import Account
from app.schemas import AccountCreateResponse, BalanceResponse
from app.services.accounts import create_account

router = APIRouter(prefix="/v1", tags=["accounts"])


@router.post("/accounts", response_model=AccountCreateResponse, status_code=status.HTTP_201_CREATED)
def create_account_route(session: Annotated[Session, Depends(get_session)]) -> AccountCreateResponse:
    account, api_key = create_account(session)
    return AccountCreateResponse(
        account_id=account.id,
        api_key=api_key,
        deposit_address=account.deposit_address,
    )


@router.get("/balance", response_model=BalanceResponse)
def get_balance_route(account: Annotated[Account, Depends(get_current_account)]) -> BalanceResponse:
    return BalanceResponse(
        available_micro_usdc=account.available_micro_usdc,
        reserved_micro_usdc=account.reserved_micro_usdc,
    )

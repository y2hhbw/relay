from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.models import Account
from app.services.accounts import get_account_by_api_key


def get_session(request: Request) -> Generator[Session, None, None]:
    for session in get_db_session(request.app.state.session_factory):
        session.info["rate_limiter"] = request.app.state.rate_limiter
        session.info["settings"] = request.app.state.settings
        yield session


def get_current_account(
    session: Annotated[Session, Depends(get_session)],
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Account:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    account = get_account_by_api_key(session, api_key)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    return account

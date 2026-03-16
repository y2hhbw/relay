import hashlib
import secrets

from sqlalchemy.orm import Session

from app.models import Account


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def create_account(session: Session) -> tuple[Account, str]:
    api_key = f"relay_{secrets.token_urlsafe(24)}"
    account = Account(
        id=secrets.token_hex(16),
        deposit_address=f"0x{secrets.token_hex(20)}",
        api_key_hash=hash_api_key(api_key),
        available_micro_usdc=0,
        reserved_micro_usdc=0,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account, api_key


def get_account_by_api_key(session: Session, api_key: str) -> Account | None:
    api_key_hash = hash_api_key(api_key)
    return session.query(Account).filter(Account.api_key_hash == api_key_hash).one_or_none()

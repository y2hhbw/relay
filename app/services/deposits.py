from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, Deposit, LedgerEntry


def apply_confirmed_deposit(
    session: Session,
    *,
    tx_hash: str,
    log_index: int,
    deposit_address: str,
    amount_micro_usdc: int,
) -> str:
    existing = (
        session.query(Deposit)
        .filter(Deposit.tx_hash == tx_hash, Deposit.log_index == log_index)
        .one_or_none()
    )
    if existing is not None:
        return "duplicate"

    account = (
        session.query(Account)
        .filter(Account.deposit_address == deposit_address)
        .one_or_none()
    )
    if account is None:
        session.add(
            Deposit(
                tx_hash=tx_hash,
                log_index=log_index,
                deposit_address=deposit_address,
                amount_micro_usdc=amount_micro_usdc,
                status="ignored",
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return "duplicate"
        return "ignored"

    account.available_micro_usdc += amount_micro_usdc
    session.add(
        Deposit(
            tx_hash=tx_hash,
            log_index=log_index,
            deposit_address=deposit_address,
            amount_micro_usdc=amount_micro_usdc,
            status="credited",
        )
    )
    session.add(
        LedgerEntry(
            account_id=account.id,
            entry_type="deposit",
            amount_micro_usdc=amount_micro_usdc,
            available_after=account.available_micro_usdc,
            reserved_after=account.reserved_micro_usdc,
            reference=f"{tx_hash}:{log_index}",
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return "duplicate"
    return "credited"

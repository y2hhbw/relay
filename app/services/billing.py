from math import ceil

from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry


def record_entry(
    session: Session,
    *,
    account: Account,
    entry_type: str,
    amount_micro_usdc: int,
    reference: str,
) -> None:
    session.add(
        LedgerEntry(
            account_id=account.id,
            entry_type=entry_type,
            amount_micro_usdc=amount_micro_usdc,
            available_after=account.available_micro_usdc,
            reserved_after=account.reserved_micro_usdc,
            reference=reference,
        )
    )


def debit_fixed_cost(session: Session, *, account: Account, amount_micro_usdc: int, reference: str) -> None:
    if account.available_micro_usdc < amount_micro_usdc:
        raise ValueError("insufficient_fixed_balance")

    account.available_micro_usdc -= amount_micro_usdc
    record_entry(
        session,
        account=account,
        entry_type="debit",
        amount_micro_usdc=-amount_micro_usdc,
        reference=reference,
    )
    session.commit()


def refund_fixed_cost(session: Session, *, account: Account, amount_micro_usdc: int, reference: str) -> None:
    account.available_micro_usdc += amount_micro_usdc
    record_entry(
        session,
        account=account,
        entry_type="refund",
        amount_micro_usdc=amount_micro_usdc,
        reference=reference,
    )
    session.commit()


def calculate_reserve(service: dict[str, int | str], *, estimated_input_tokens: int, max_output_tokens: int) -> int:
    input_rate = int(service["input_cost_per_1k_micro_usdc"])
    output_rate = int(service["output_cost_per_1k_micro_usdc"])
    buffer_bps = int(service["reserve_buffer_bps"])
    estimated_cost = ceil((estimated_input_tokens * input_rate + max_output_tokens * output_rate) / 1000)
    return ceil(estimated_cost * buffer_bps / 10000)


def reserve_amount(session: Session, *, account: Account, reserve_micro_usdc: int, reference: str) -> None:
    if account.available_micro_usdc < reserve_micro_usdc:
        raise ValueError("insufficient_reserve_balance")

    account.available_micro_usdc -= reserve_micro_usdc
    account.reserved_micro_usdc += reserve_micro_usdc
    record_entry(
        session,
        account=account,
        entry_type="reserve",
        amount_micro_usdc=-reserve_micro_usdc,
        reference=reference,
    )
    session.commit()


def settle_reserve(
    session: Session,
    *,
    account: Account,
    reserve_micro_usdc: int,
    settled_micro_usdc: int,
    reference: str,
) -> int:
    released_micro_usdc = reserve_micro_usdc - settled_micro_usdc
    account.reserved_micro_usdc -= reserve_micro_usdc
    account.available_micro_usdc += released_micro_usdc
    record_entry(
        session,
        account=account,
        entry_type="settle",
        amount_micro_usdc=-settled_micro_usdc,
        reference=reference,
    )
    record_entry(
        session,
        account=account,
        entry_type="release",
        amount_micro_usdc=released_micro_usdc,
        reference=reference,
    )
    session.commit()
    return released_micro_usdc


def release_reserve(session: Session, *, account: Account, reserve_micro_usdc: int, reference: str) -> None:
    account.reserved_micro_usdc -= reserve_micro_usdc
    account.available_micro_usdc += reserve_micro_usdc
    record_entry(
        session,
        account=account,
        entry_type="release",
        amount_micro_usdc=reserve_micro_usdc,
        reference=reference,
    )
    session.commit()

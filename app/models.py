from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    deposit_address: Mapped[str] = mapped_column(String(42), unique=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    available_micro_usdc: Mapped[int] = mapped_column(Integer, default=0)
    reserved_micro_usdc: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Deposit(Base):
    __tablename__ = "deposits"
    __table_args__ = (UniqueConstraint("tx_hash", "log_index", name="uq_deposits_tx_log"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tx_hash: Mapped[str] = mapped_column(String(66))
    log_index: Mapped[int] = mapped_column(Integer)
    deposit_address: Mapped[str] = mapped_column(String(42), index=True)
    amount_micro_usdc: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="credited")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(32), index=True)
    entry_type: Mapped[str] = mapped_column(String(32))
    amount_micro_usdc: Mapped[int] = mapped_column(Integer)
    available_after: Mapped[int] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ApiCall(Base):
    __tablename__ = "api_calls"
    __table_args__ = (
        Index("ix_api_calls_account_seq", "account_id", "sequence_id"),
        Index("ix_api_calls_account_created", "account_id", "created_at"),
        Index("ix_api_calls_account_service_status_created", "account_id", "service_key", "status", "created_at"),
    )

    sequence_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    account_id: Mapped[str] = mapped_column(String(32), index=True)
    service_key: Mapped[str] = mapped_column(String(64), index=True)
    pricing_mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    reserved_micro_usdc: Mapped[int] = mapped_column(Integer, default=0)
    settled_micro_usdc: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

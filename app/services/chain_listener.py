from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from sqlalchemy.orm import Session, sessionmaker

from app.services.deposits import apply_confirmed_deposit


@dataclass(frozen=True)
class TransferEvent:
    tx_hash: str
    log_index: int
    to_address: str
    amount_base_units: int
    block_number: int


@dataclass(frozen=True)
class ChainListenerConfig:
    start_block: int
    poll_interval_seconds: float = 2.0
    confirmations: int = 0
    state_file_path: str = ".relay-listener-state.json"
    retry_backoff_seconds: float = 1.0
    max_retry_backoff_seconds: float = 30.0
    alert_after_consecutive_failures: int = 5
    alert_cooldown_seconds: float = 60.0


@dataclass
class ListenerMetrics:
    poll_success_total: int = 0
    poll_failure_total: int = 0
    consecutive_failure_count: int = 0
    last_success_epoch: float = 0.0


class HttpWebhookAlertSink:
    def __init__(self, *, webhook_url: str, timeout_seconds: float = 5.0):
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds

    def send(self, message: str) -> None:
        response = httpx.post(
            self._webhook_url,
            json={"text": message},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()


class TransferEventSource(Protocol):
    def get_latest_block(self) -> int: ...

    def get_transfer_events(self, from_block: int, to_block: int) -> list[TransferEvent]: ...


class USDCTransferListener:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        event_source: TransferEventSource,
        config: ChainListenerConfig,
        alert_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._session_factory = session_factory
        self._event_source = event_source
        self._config = config
        self._alert_callback = alert_callback
        self._last_processed_block = self._load_last_processed_block()
        self._metrics = ListenerMetrics()
        self._last_alert_epoch = 0.0

    def _load_last_processed_block(self) -> int:
        state_file = Path(self._config.state_file_path)
        if not state_file.exists():
            return self._config.start_block - 1
        try:
            payload = json.loads(state_file.read_text())
            return int(payload.get("last_processed_block", self._config.start_block - 1))
        except Exception:
            return self._config.start_block - 1

    def _persist_last_processed_block(self) -> None:
        state_file = Path(self._config.state_file_path)
        state_file.write_text(json.dumps({"last_processed_block": self._last_processed_block}))

    def poll_once(self) -> dict[str, int]:
        latest_block = self._event_source.get_latest_block() - self._config.confirmations
        if latest_block <= self._last_processed_block:
            return {
                "credited": 0,
                "duplicate": 0,
                "ignored": 0,
                "last_processed_block": self._last_processed_block,
            }

        from_block = self._last_processed_block + 1
        events = self._event_source.get_transfer_events(from_block, latest_block)

        counts = {"credited": 0, "duplicate": 0, "ignored": 0}
        session = self._session_factory()
        try:
            for event in events:
                result = apply_confirmed_deposit(
                    session,
                    tx_hash=event.tx_hash,
                    log_index=event.log_index,
                    deposit_address=event.to_address.lower(),
                    amount_micro_usdc=event.amount_base_units,
                )
                if result in counts:
                    counts[result] += 1
            self._last_processed_block = latest_block
            self._persist_last_processed_block()
        finally:
            session.close()

        return {
            "credited": counts["credited"],
            "duplicate": counts["duplicate"],
            "ignored": counts["ignored"],
            "last_processed_block": self._last_processed_block,
        }

    def run_forever(self, *, max_cycles: int | None = None) -> None:
        cycles = 0

        while True:
            if max_cycles is not None and cycles >= max_cycles:
                break

            try:
                self.poll_once()
                self._metrics.poll_success_total += 1
                self._metrics.consecutive_failure_count = 0
                self._metrics.last_success_epoch = time.time()
                self._last_alert_epoch = 0.0
                time.sleep(self._config.poll_interval_seconds)
            except Exception as exc:
                self._metrics.poll_failure_total += 1
                self._metrics.consecutive_failure_count += 1
                backoff_seconds = min(
                    self._config.retry_backoff_seconds * (2 ** (self._metrics.consecutive_failure_count - 1)),
                    self._config.max_retry_backoff_seconds,
                )
                self._logger.exception(
                    "listener poll failed (consecutive=%s)",
                    self._metrics.consecutive_failure_count,
                )
                if (
                    self._alert_callback
                    and self._metrics.consecutive_failure_count >= self._config.alert_after_consecutive_failures
                ):
                    now = time.time()
                    if (
                        self._last_alert_epoch == 0.0
                        or now - self._last_alert_epoch >= self._config.alert_cooldown_seconds
                    ):
                        self._alert_callback(
                            f"listener consecutive failures: {self._metrics.consecutive_failure_count}: {exc}"
                        )
                        self._last_alert_epoch = now
                time.sleep(backoff_seconds)

            cycles += 1

    def metrics_snapshot(self) -> dict[str, float | int]:
        return {
            "poll_success_total": self._metrics.poll_success_total,
            "poll_failure_total": self._metrics.poll_failure_total,
            "consecutive_failure_count": self._metrics.consecutive_failure_count,
            "last_success_epoch": self._metrics.last_success_epoch,
        }


class Web3TransferEventSource:
    def __init__(self, *, rpc_url: str, token_contract_address: str):
        try:
            from web3 import Web3
        except ImportError as exc:
            raise RuntimeError("web3 package is required for on-chain listener mode") from exc

        self._web3 = Web3(Web3.HTTPProvider(rpc_url))
        self._contract_address = self._web3.to_checksum_address(token_contract_address)
        self._transfer_topic = self._web3.keccak(text="Transfer(address,address,uint256)").hex()

    def get_latest_block(self) -> int:
        return int(self._web3.eth.block_number)

    def get_transfer_events(self, from_block: int, to_block: int) -> list[TransferEvent]:
        logs = self._web3.eth.get_logs(
            {
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": self._contract_address,
                "topics": [self._transfer_topic],
            }
        )

        events: list[TransferEvent] = []
        for log in logs:
            to_topic = log["topics"][2].hex()
            to_address = f"0x{to_topic[-40:]}".lower()
            amount = int(log["data"], 16)
            events.append(
                TransferEvent(
                    tx_hash=log["transactionHash"].hex(),
                    log_index=int(log["logIndex"]),
                    to_address=to_address,
                    amount_base_units=amount,
                    block_number=int(log["blockNumber"]),
                )
            )
        return events

from app.db import Base, create_session_factory
from app.models import Account
from app.services.chain_listener import (
    ChainListenerConfig,
    HttpWebhookAlertSink,
    TransferEvent,
    USDCTransferListener,
)


class _FakeEventSource:
    def __init__(self, latest_block: int, events_by_block: dict[int, list[TransferEvent]]):
        self.latest_block = latest_block
        self.events_by_block = events_by_block

    def get_latest_block(self) -> int:
        return self.latest_block

    def get_transfer_events(self, from_block: int, to_block: int) -> list[TransferEvent]:
        events: list[TransferEvent] = []
        for block in range(from_block, to_block + 1):
            events.extend(self.events_by_block.get(block, []))
        return events


def _seed_account(session_factory, deposit_address: str) -> None:
    session = session_factory()
    try:
        session.add(
            Account(
                id="acc_1",
                deposit_address=deposit_address,
                api_key_hash="hash",
                available_micro_usdc=0,
                reserved_micro_usdc=0,
            )
        )
        session.commit()
    finally:
        session.close()


def test_listener_credits_matching_deposit_and_advances_block(tmp_path):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])
    _seed_account(session_factory, "0x1111111111111111111111111111111111111111")

    source = _FakeEventSource(
        latest_block=105,
        events_by_block={
            105: [
                TransferEvent(
                    tx_hash="0xtx1",
                    log_index=0,
                    to_address="0x1111111111111111111111111111111111111111",
                    amount_base_units=1_250_000,
                    block_number=105,
                )
            ]
        },
    )
    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=source,
        config=ChainListenerConfig(start_block=100, state_file_path=str(tmp_path / "state-1.json")),
    )

    result = listener.poll_once()

    assert result["credited"] == 1
    assert result["last_processed_block"] == 105

    session = session_factory()
    try:
        account = session.query(Account).filter(Account.id == "acc_1").one()
        assert account.available_micro_usdc == 1_250_000
    finally:
        session.close()


def test_listener_is_idempotent_for_duplicate_events(tmp_path):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])
    _seed_account(session_factory, "0x2222222222222222222222222222222222222222")

    event = TransferEvent(
        tx_hash="0xtx2",
        log_index=3,
        to_address="0x2222222222222222222222222222222222222222",
        amount_base_units=900_000,
        block_number=200,
    )
    source = _FakeEventSource(latest_block=200, events_by_block={200: [event, event]})
    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=source,
        config=ChainListenerConfig(start_block=200, state_file_path=str(tmp_path / "state-2.json")),
    )

    result = listener.poll_once()

    assert result["credited"] == 1
    assert result["duplicate"] == 1

    session = session_factory()
    try:
        account = session.query(Account).filter(Account.id == "acc_1").one()
        assert account.available_micro_usdc == 900_000
    finally:
        session.close()


def test_listener_ignores_unknown_deposit_address(tmp_path):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])

    source = _FakeEventSource(
        latest_block=301,
        events_by_block={
            301: [
                TransferEvent(
                    tx_hash="0xtx3",
                    log_index=0,
                    to_address="0x3333333333333333333333333333333333333333",
                    amount_base_units=500_000,
                    block_number=301,
                )
            ]
        },
    )
    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=source,
        config=ChainListenerConfig(start_block=300, state_file_path=str(tmp_path / "state-3.json")),
    )

    result = listener.poll_once()

    assert result["ignored"] == 1


def test_listener_retries_after_failure_and_continues(tmp_path, monkeypatch):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])

    class FlakySource:
        def __init__(self):
            self.calls = 0

        def get_latest_block(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary rpc failure")
            return 100

        def get_transfer_events(self, from_block: int, to_block: int):
            del from_block
            del to_block
            return []

    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.chain_listener.time.sleep", lambda sec: sleep_calls.append(sec))

    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=FlakySource(),
        config=ChainListenerConfig(
            start_block=100,
            state_file_path=str(tmp_path / "state-retry.json"),
            poll_interval_seconds=0.1,
            retry_backoff_seconds=0.5,
        ),
    )

    listener.run_forever(max_cycles=2)

    assert sleep_calls[0] == 0.5
    assert sleep_calls[1] == 0.1


def test_listener_alerts_after_consecutive_failures(tmp_path, monkeypatch):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])

    class BrokenSource:
        def get_latest_block(self):
            raise RuntimeError("rpc down")

        def get_transfer_events(self, from_block: int, to_block: int):
            del from_block
            del to_block
            return []

    monkeypatch.setattr("app.services.chain_listener.time.sleep", lambda sec: None)
    alerts: list[str] = []

    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=BrokenSource(),
        config=ChainListenerConfig(
            start_block=100,
            state_file_path=str(tmp_path / "state-alert.json"),
            alert_after_consecutive_failures=2,
        ),
        alert_callback=alerts.append,
    )

    listener.run_forever(max_cycles=2)

    assert len(alerts) == 1
    assert "consecutive failures" in alerts[0]


def test_listener_exposes_runtime_metrics(tmp_path, monkeypatch):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])

    class FlakySource:
        def __init__(self):
            self.calls = 0

        def get_latest_block(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("rpc down")
            return 120

        def get_transfer_events(self, from_block: int, to_block: int):
            del from_block
            del to_block
            return []

    monkeypatch.setattr("app.services.chain_listener.time.sleep", lambda sec: None)

    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=FlakySource(),
        config=ChainListenerConfig(
            start_block=120,
            state_file_path=str(tmp_path / "state-metrics.json"),
            alert_after_consecutive_failures=99,
        ),
    )

    listener.run_forever(max_cycles=2)
    metrics = listener.metrics_snapshot()

    assert metrics["poll_success_total"] == 1
    assert metrics["poll_failure_total"] == 1
    assert metrics["consecutive_failure_count"] == 0
    assert metrics["last_success_epoch"] > 0


def test_webhook_alert_sink_posts_json_payload(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        sent["timeout"] = timeout

        class Response:
            @staticmethod
            def raise_for_status():
                return None

        return Response()

    monkeypatch.setattr("app.services.chain_listener.httpx.post", fake_post)

    sink = HttpWebhookAlertSink(webhook_url="https://example.com/hook", timeout_seconds=3.0)
    sink.send("listener failure")

    assert sent["url"] == "https://example.com/hook"
    assert sent["json"] == {"text": "listener failure"}
    assert sent["timeout"] == 3.0


def test_listener_alert_cooldown_prevents_alert_spam(tmp_path, monkeypatch):
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=session_factory.kw["bind"])

    class BrokenSource:
        def get_latest_block(self):
            raise RuntimeError("rpc down")

        def get_transfer_events(self, from_block: int, to_block: int):
            del from_block
            del to_block
            return []

    monkeypatch.setattr("app.services.chain_listener.time.sleep", lambda sec: None)
    now_values = iter([10.0, 20.0, 30.0, 95.0])
    monkeypatch.setattr("app.services.chain_listener.time.time", lambda: next(now_values))

    alerts: list[str] = []
    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=BrokenSource(),
        config=ChainListenerConfig(
            start_block=100,
            state_file_path=str(tmp_path / "state-cooldown.json"),
            alert_after_consecutive_failures=2,
            alert_cooldown_seconds=60.0,
        ),
        alert_callback=alerts.append,
    )

    listener.run_forever(max_cycles=5)

    assert len(alerts) == 2

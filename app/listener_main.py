import logging

from app.config import Settings
from app.db import Base, create_session_factory
from app.services.chain_listener import (
    ChainListenerConfig,
    HttpWebhookAlertSink,
    USDCTransferListener,
    Web3TransferEventSource,
)


def run_listener() -> None:
    settings = Settings()
    if not settings.chain_listener_rpc_url:
        raise RuntimeError("RELAY_CHAIN_LISTENER_RPC_URL is required")
    if not settings.chain_listener_token_contract_address:
        raise RuntimeError("RELAY_CHAIN_LISTENER_TOKEN_CONTRACT_ADDRESS is required")

    session_factory = create_session_factory(settings.database_url)
    Base.metadata.create_all(bind=session_factory.kw["bind"])

    source = Web3TransferEventSource(
        rpc_url=settings.chain_listener_rpc_url,
        token_contract_address=settings.chain_listener_token_contract_address,
    )

    logger = logging.getLogger(__name__)
    webhook_sink = (
        HttpWebhookAlertSink(webhook_url=settings.chain_listener_alert_webhook_url)
        if settings.chain_listener_alert_webhook_url
        else None
    )

    def alert_callback(message: str) -> None:
        logger.error(message)
        if webhook_sink is None:
            return
        try:
            webhook_sink.send(message)
        except Exception:
            logger.exception("failed to send webhook alert")

    listener = USDCTransferListener(
        session_factory=session_factory,
        event_source=source,
        config=ChainListenerConfig(
            start_block=settings.chain_listener_start_block,
            poll_interval_seconds=settings.chain_listener_poll_interval_seconds,
            confirmations=settings.chain_listener_confirmations,
            state_file_path=settings.chain_listener_state_file_path,
            retry_backoff_seconds=settings.chain_listener_retry_backoff_seconds,
            max_retry_backoff_seconds=settings.chain_listener_max_retry_backoff_seconds,
            alert_after_consecutive_failures=settings.chain_listener_alert_after_consecutive_failures,
            alert_cooldown_seconds=settings.chain_listener_alert_cooldown_seconds,
        ),
        alert_callback=alert_callback,
    )
    listener.run_forever()


if __name__ == "__main__":
    run_listener()

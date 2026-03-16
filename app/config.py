from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    search_provider_mode: str = "mock"
    search_provider_timeout_seconds: float = 5.0
    database_url: str = "sqlite+pysqlite:///./relay.db"
    chain_listener_rpc_url: str = ""
    chain_listener_token_contract_address: str = ""
    chain_listener_start_block: int = 0
    chain_listener_confirmations: int = 2
    chain_listener_poll_interval_seconds: float = 2.0
    chain_listener_state_file_path: str = ".relay-listener-state.json"
    chain_listener_retry_backoff_seconds: float = 1.0
    chain_listener_max_retry_backoff_seconds: float = 30.0
    chain_listener_alert_after_consecutive_failures: int = 5
    chain_listener_alert_cooldown_seconds: float = 60.0
    chain_listener_alert_webhook_url: str = ""

    model_config = SettingsConfigDict(env_prefix="RELAY_", extra="ignore")

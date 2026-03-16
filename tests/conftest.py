from collections.abc import Iterator
import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app("sqlite+pysqlite:///:memory:")
    with TestClient(app) as test_client:
        yield test_client


def create_funded_account(client: TestClient, amount_micro_usdc: int = 500_000) -> dict[str, str]:
    account = client.post("/v1/accounts").json()
    client.post(
        "/internal/deposits/confirm",
        json={
            "tx_hash": f"0x{secrets.token_hex(12)}",
            "log_index": 0,
            "deposit_address": account["deposit_address"],
            "amount_micro_usdc": amount_micro_usdc,
        },
    )
    return account

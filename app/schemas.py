from pydantic import BaseModel, ConfigDict


class AccountCreateResponse(BaseModel):
    account_id: str
    api_key: str
    deposit_address: str


class BalanceResponse(BaseModel):
    available_micro_usdc: int
    reserved_micro_usdc: int


class DepositConfirmRequest(BaseModel):
    tx_hash: str
    log_index: int
    deposit_address: str
    amount_micro_usdc: int


class DepositConfirmResponse(BaseModel):
    status: str


class SearchCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str


class OcrCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_url: str


class LlmCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    model: str
    max_output_tokens: int


class ApiCallItem(BaseModel):
    id: str
    service_key: str
    pricing_mode: str
    status: str
    reserved_micro_usdc: int
    settled_micro_usdc: int
    error_text: str


class ApiCallListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    next_cursor: str | None = None
    items: list[ApiCallItem]

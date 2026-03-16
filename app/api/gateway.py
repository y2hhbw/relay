import base64
import json
import secrets
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_account, get_session
from app.catalog import get_service
from app.config import Settings
from app.models import Account, ApiCall
from app.providers.llm import run_chat
from app.providers.search import SearchProviderError, search_web
from app.schemas import ApiCallItem, ApiCallListResponse, LlmCallRequest, OcrCallRequest, SearchCallRequest
from app.services.billing import (
    calculate_reserve,
    debit_fixed_cost,
    refund_fixed_cost,
    release_reserve,
    reserve_amount,
    settle_reserve,
)

router = APIRouter(prefix="/v1", tags=["gateway"])


def _validate_payload(service_key: str, payload: dict[str, Any]) -> SearchCallRequest | OcrCallRequest | LlmCallRequest:
    try:
        if service_key == "search.web":
            return SearchCallRequest.model_validate(payload)
        if service_key == "ocr.parse_image":
            return OcrCallRequest.model_validate(payload)
        if service_key == "llm.chat":
            return LlmCallRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors()) from exc

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported service")


def _encode_cursor(sequence_id: int) -> str:
    payload = {"sequence_id": sequence_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw)
        sequence_id = int(payload["sequence_id"])
        if sequence_id <= 0:
            raise ValueError("sequence_id must be positive")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from exc
    return sequence_id


@router.post("/calls/{service_key:path}")
def call_service_route(
    service_key: str,
    payload: dict[str, Any],
    account: Annotated[Account, Depends(get_current_account)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    service = get_service(service_key)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown service")

    validated = _validate_payload(service_key, payload)

    limiter = session.info.get("rate_limiter")
    if limiter is not None and not limiter.check(account.id, service_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    settings = session.info.get("settings")
    if not isinstance(settings, Settings):
        settings = Settings()

    reference = f"call:{service_key}:{secrets.token_hex(6)}"
    call_record = ApiCall(
        id=secrets.token_hex(16),
        account_id=account.id,
        service_key=service_key,
        pricing_mode=str(service["pricing_mode"]),
        status="started",
        reserved_micro_usdc=0,
        settled_micro_usdc=0,
        error_text="",
    )
    session.add(call_record)
    session.commit()

    if service["pricing_mode"] == "fixed":
        cost = int(service["fixed_cost_micro_usdc"])
        try:
            debit_fixed_cost(session, account=account, amount_micro_usdc=cost, reference=reference)
        except ValueError as exc:
            if str(exc) == "insufficient_fixed_balance":
                call_record.status = "rejected"
                call_record.error_text = "insufficient_fixed_balance"
                session.commit()
                raise HTTPException(status_code=402, detail="Insufficient available balance") from exc
            raise

        try:
            if service_key == "search.web":
                query_payload = validated
                assert isinstance(query_payload, SearchCallRequest)
                result = search_web(
                    query_payload.query,
                    provider_mode=settings.search_provider_mode,
                    timeout_seconds=settings.search_provider_timeout_seconds,
                )
            elif service_key == "ocr.parse_image":
                ocr_payload = validated
                assert isinstance(ocr_payload, OcrCallRequest)
                result = {"text": f"OCR text for {ocr_payload.image_url}"}
            else:
                raise HTTPException(status_code=404, detail="Unsupported service")
        except SearchProviderError as exc:
            refund_fixed_cost(session, account=account, amount_micro_usdc=cost, reference=reference)
            call_record.status = "failed"
            call_record.error_text = "upstream_provider_failed"
            session.commit()
            raise HTTPException(status_code=502, detail="Upstream provider failed") from exc

        call_record.status = "succeeded"
        call_record.settled_micro_usdc = cost
        session.commit()

        return {
            "service_key": service_key,
            "billing": {
                "pricing_mode": "fixed",
                "debited_micro_usdc": cost,
            },
            "result": result,
        }

    estimated_input_tokens = 100
    llm_payload = validated
    assert isinstance(llm_payload, LlmCallRequest)
    max_output_tokens = llm_payload.max_output_tokens
    reserve_micro_usdc = calculate_reserve(
        service,
        estimated_input_tokens=estimated_input_tokens,
        max_output_tokens=max_output_tokens,
    )

    try:
        reserve_amount(session, account=account, reserve_micro_usdc=reserve_micro_usdc, reference=reference)
    except ValueError as exc:
        if str(exc) == "insufficient_reserve_balance":
            call_record.status = "rejected"
            call_record.error_text = "insufficient_reserve_balance"
            session.commit()
            raise HTTPException(status_code=402, detail="Insufficient available balance for reserve") from exc
        raise

    call_record.reserved_micro_usdc = reserve_micro_usdc
    session.commit()

    try:
        result = run_chat(
            prompt=llm_payload.prompt,
            model=llm_payload.model,
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        release_reserve(session, account=account, reserve_micro_usdc=reserve_micro_usdc, reference=reference)
        call_record.status = "failed"
        call_record.error_text = "upstream_provider_failed"
        session.commit()
        raise HTTPException(status_code=502, detail="Upstream provider failed") from exc

    usage = cast(dict[str, int], result["usage"])
    settled_micro_usdc = (
        int(usage["input_tokens"]) * int(service["input_cost_per_1k_micro_usdc"])
        + int(usage["output_tokens"]) * int(service["output_cost_per_1k_micro_usdc"])
    ) // 1000
    released_micro_usdc = settle_reserve(
        session,
        account=account,
        reserve_micro_usdc=reserve_micro_usdc,
        settled_micro_usdc=settled_micro_usdc,
        reference=reference,
    )
    call_record.status = "succeeded"
    call_record.settled_micro_usdc = settled_micro_usdc
    session.commit()
    return {
        "service_key": service_key,
        "billing": {
            "pricing_mode": "reserve_then_settle",
            "reserved_micro_usdc": reserve_micro_usdc,
            "settled_micro_usdc": settled_micro_usdc,
            "released_micro_usdc": released_micro_usdc,
        },
        "result": {"content": result["content"]},
    }


@router.get("/calls", response_model=ApiCallListResponse)
def list_calls_route(
    account: Annotated[Account, Depends(get_current_account)],
    session: Annotated[Session, Depends(get_session)],
    service_key: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    cursor: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ApiCallListResponse:
    if start_at and end_at and start_at > end_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_at must be earlier than or equal to end_at",
        )

    query = session.query(ApiCall).filter(ApiCall.account_id == account.id)

    if service_key:
        query = query.filter(ApiCall.service_key == service_key)
    if status_filter:
        query = query.filter(ApiCall.status == status_filter)
    if start_at:
        query = query.filter(ApiCall.created_at >= start_at)
    if end_at:
        query = query.filter(ApiCall.created_at <= end_at)

    cursor_sequence_id = _decode_cursor(cursor) if cursor else None
    effective_offset = offset

    if cursor_sequence_id is not None:
        query = query.filter(ApiCall.sequence_id < cursor_sequence_id)
        effective_offset = 0

    total = query.count()
    ordered = query.order_by(ApiCall.sequence_id.desc())
    rows = ordered.offset(effective_offset).limit(limit + 1).all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = _encode_cursor(page_rows[-1].sequence_id) if has_more and page_rows else None

    items = [
        ApiCallItem(
            id=row.id,
            service_key=row.service_key,
            pricing_mode=row.pricing_mode,
            status=row.status,
            reserved_micro_usdc=row.reserved_micro_usdc,
            settled_micro_usdc=row.settled_micro_usdc,
            error_text=row.error_text,
        )
        for row in page_rows
    ]
    return ApiCallListResponse(total=total, limit=limit, offset=effective_offset, next_cursor=next_cursor, items=items)

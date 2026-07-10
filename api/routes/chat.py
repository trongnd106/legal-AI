"""Routes chat — hỏi đáp luật lao động."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.services.graph_loader import artifacts_available, get_loader_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

CHAT_TIMEOUT_SECONDS = 90


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    mode: Literal["local", "global"] = "local"
    domain: str | None = "lao_dong"


class DataCitationItem(BaseModel):
    key: str
    type: str
    id: str
    label: str
    detail: str
    icon: str = "📎"
    type_label: str = ""


class ChatResponse(BaseModel):
    answer: str
    mode: str
    article_citations: list[str]
    entities_used: list[str] = Field(default_factory=list)
    temporal_warnings: list[str] = Field(default_factory=list)
    data_citations: list[DataCitationItem] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    try:
        from query.citation_resolver import resolve_data_citations
        from query.global_search import ask_global
        from query.local_search import ask_local
        from query.temporal_filter import filter_citations_by_effectiveness
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "GraphRAG chưa cài đặt. Chạy từ repo root: "
                "pip install -e packages/graphrag && pip install -r api/requirements.txt"
            ),
        ) from exc

    if not artifacts_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "GraphRAG chưa sẵn sàng. Chạy: "
                ".venv/bin/graphrag index --root data/labor-law"
            ),
        )

    question = body.question.strip()
    try:
        # get_loader_async chạy trong thread pool → không block event loop, không xung đột asyncio.run()
        try:
            loader = await get_loader_async()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        if body.mode == "global":
            coro = ask_global(
                question,
                loader,
                domain_filter=body.domain,
                response_type="multiple paragraphs",
            )
            entities: list[str] = []
        else:
            coro = ask_local(
                question,
                loader,
                response_type="multiple paragraphs",
            )
            entities = []

        try:
            result = await asyncio.wait_for(coro, timeout=CHAT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("Chat request timed out after %ss", CHAT_TIMEOUT_SECONDS)
            raise HTTPException(
                status_code=504,
                detail=(
                    f"Hệ thống mất quá nhiều thời gian để xử lý (>{CHAT_TIMEOUT_SECONDS}s). "
                    "Vui lòng thử lại hoặc đặt câu hỏi ngắn gọn hơn."
                ),
            )

        if body.mode != "global":
            entities = result.get("entities_used", [])

        answer = str(result.get("answer", ""))
        citations = list(result.get("article_citations", []))
        context_data = result.get("context_data")
        data_citations = resolve_data_citations(answer, context_data)

        temporal = filter_citations_by_effectiveness(citations)
        warnings = temporal.get("expired_warnings", [])

        return ChatResponse(
            answer=answer,
            mode=body.mode,
            article_citations=citations,
            entities_used=entities[:20],
            temporal_warnings=warnings,
            data_citations=[DataCitationItem(**item) for item in data_citations],
        )
    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise HTTPException(
            status_code=503,
            detail="Yêu cầu bị hủy. Vui lòng thử lại.",
        )
    except Exception as exc:
        exc_str = str(exc)
        logger.exception("Chat error: %s", exc_str[:200])
        # Kiểm tra RateLimitError / model overload
        if "RateLimitError" in exc_str or "429" in exc_str or "engine_overloaded" in exc_str:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Model AI đang quá tải, vui lòng thử lại sau 1-2 phút. "
                    "(OpenRouter: Model busy / Rate limit)"
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=exc_str) from exc


async def _stream_chat(body: ChatRequest) -> AsyncGenerator[str, None]:
    """SSE generator — yield từng token rồi gửi metadata khi hoàn tất."""
    try:
        from query.citation_resolver import resolve_data_citations
        from query.global_search import ask_global_streaming
        from query.local_search import ask_local_streaming
        from query.temporal_filter import filter_citations_by_effectiveness
    except ImportError as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return

    if not artifacts_available():
        yield f"data: {json.dumps({'type': 'error', 'message': 'GraphRAG chưa sẵn sàng'}, ensure_ascii=False)}\n\n"
        return

    question = body.question.strip()
    try:
        loader = await get_loader_async()
    except FileNotFoundError as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return

    done_data: dict[str, Any] | None = None
    mode = body.mode

    try:
        if mode == "global":
            gen = ask_global_streaming(
                question,
                loader,
                domain_filter=body.domain,
                response_type="multiple paragraphs",
            )
        else:
            gen = ask_local_streaming(
                question,
                loader,
                response_type="multiple paragraphs",
            )

        async for item in gen:
            if isinstance(item, dict) and item.get("type") == "done":
                done_data = item
                break
            yield f"data: {json.dumps({'type': 'token', 'content': item}, ensure_ascii=False)}\n\n"

    except asyncio.CancelledError:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Yêu cầu bị hủy'}, ensure_ascii=False)}\n\n"
        return
    except Exception as exc:
        exc_str = str(exc)
        logger.exception("Stream chat error: %s", exc_str[:200])
        if "RateLimitError" in exc_str or "429" in exc_str or "engine_overloaded" in exc_str:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Model AI đang quá tải, vui lòng thử lại sau 1-2 phút.'}, ensure_ascii=False)}\n\n"
            return
        yield f"data: {json.dumps({'type': 'error', 'message': exc_str}, ensure_ascii=False)}\n\n"
        return

    if done_data is None:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Không nhận được kết quả từ GraphRAG'}, ensure_ascii=False)}\n\n"
        return

    answer = done_data.get("answer", "")
    article_citations = done_data.get("article_citations", [])
    context_data = done_data.get("context_data")
    entities_used = done_data.get("entities_used", [])

    data_citations = resolve_data_citations(answer, context_data) if context_data else []
    temporal = filter_citations_by_effectiveness(article_citations)
    warnings = temporal.get("expired_warnings", [])

    done_event = {
        "type": "done",
        "answer": answer,
        "mode": mode,
        "article_citations": article_citations,
        "entities_used": entities_used[:20],
        "temporal_warnings": warnings,
        "data_citations": data_citations,
    }
    yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream_chat(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

"""Routes chat — hỏi đáp luật lao động."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services.graph_loader import artifacts_available, get_loader_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

CHAT_TIMEOUT_SECONDS = 90


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    mode: Literal["local", "global"] = "local"
    domain: str | None = "lao_dong"


class ChatResponse(BaseModel):
    answer: str
    mode: str
    article_citations: list[str]
    entities_used: list[str] = Field(default_factory=list)
    temporal_warnings: list[str] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    try:
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

        temporal = filter_citations_by_effectiveness(citations)
        warnings = temporal.get("expired_warnings", [])

        return ChatResponse(
            answer=answer,
            mode=body.mode,
            article_citations=citations,
            entities_used=entities[:20],
            temporal_warnings=warnings,
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

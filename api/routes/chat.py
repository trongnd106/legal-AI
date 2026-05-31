"""Routes chat — hỏi đáp luật lao động."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services.graph_loader import artifacts_available, get_loader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


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

    try:
        loader = get_loader()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    question = body.question.strip()
    try:
        if body.mode == "global":
            result = await ask_global(
                question,
                loader,
                domain_filter=body.domain,
                response_type="multiple paragraphs",
            )
            entities: list[str] = []
        else:
            result = await ask_local(
                question,
                loader,
                response_type="multiple paragraphs",
            )
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
    except Exception as exc:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

"""Routes lịch sử trò chuyện — mỗi session một file trong ~/.legalai/sessions/."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services import chat_history as store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat-sessions"])


class DataCitationItem(BaseModel):
    key: str
    type: str
    id: str
    label: str
    detail: str
    icon: str | None = None
    type_label: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "bot"]
    html: str | None = None
    markdown: str | None = None
    plain: str | None = None
    citations: list[str] | None = None
    dataCitations: list[DataCitationItem] | None = None
    timestamp: int | None = None


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    createdAt: int
    updatedAt: int


class ChatSession(ChatSessionSummary):
    messages: list[ChatMessage]


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionSummary]
    activeSessionId: str
    storagePath: str


class CreateSessionRequest(BaseModel):
    id: str | None = None
    title: str | None = None
    messages: list[ChatMessage] | None = None


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    messages: list[ChatMessage] | None = None


class SetActiveSessionRequest(BaseModel):
    activeSessionId: str = Field(..., min_length=1)


def _to_session(data: dict) -> ChatSession:
    return ChatSession(**data)


def _to_summary(data: dict) -> ChatSessionSummary:
    return ChatSessionSummary(
        id=data["id"],
        title=data["title"],
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


@router.get("/chat-sessions", response_model=ChatSessionListResponse)
def list_chat_sessions() -> ChatSessionListResponse:
    data = store.list_session_summaries()
    return ChatSessionListResponse(
        sessions=[_to_summary(s) for s in data["sessions"]],
        activeSessionId=data["activeSessionId"],
        storagePath=data["storagePath"],
    )


@router.get("/chat-sessions/{session_id}", response_model=ChatSession)
def get_chat_session(session_id: str) -> ChatSession:
    data = store.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
    return _to_session(data)


@router.post("/chat-sessions", response_model=ChatSession)
def create_chat_session(body: CreateSessionRequest | None = None) -> ChatSession:
    payload = body or CreateSessionRequest()
    try:
        data = store.create_session(
            session_id=payload.id,
            title=payload.title or store.DEFAULT_NEW_CHAT_TITLE,
            messages=(
                [m.model_dump() for m in payload.messages]
                if payload.messages is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Không tạo được session")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_session(data)


@router.put("/chat-sessions/{session_id}", response_model=ChatSession)
def update_chat_session(session_id: str, body: UpdateSessionRequest) -> ChatSession:
    try:
        data = store.update_session(
            session_id,
            title=body.title,
            messages=(
                [m.model_dump() for m in body.messages]
                if body.messages is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Không cập nhật được session %s", session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if data is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
    return _to_session(data)


@router.patch("/chat-sessions/active", response_model=ChatSessionListResponse)
def set_active_chat_session(body: SetActiveSessionRequest) -> ChatSessionListResponse:
    if not store.set_active_session(body.activeSessionId):
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
    data = store.list_session_summaries()
    return ChatSessionListResponse(
        sessions=[_to_summary(s) for s in data["sessions"]],
        activeSessionId=data["activeSessionId"],
        storagePath=data["storagePath"],
    )

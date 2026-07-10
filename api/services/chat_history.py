"""Lưu / đọc lịch sử trò chuyện trong ~/.legalai — mỗi session một file."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from api.config import (
    CHAT_HISTORY_LEGACY_PATH,
    CHAT_INDEX_PATH,
    CHAT_SESSIONS_DIR,
    LEGALAI_DIR,
)

logger = logging.getLogger(__name__)

DEFAULT_NEW_CHAT_TITLE = "Cuộc trò chuyện mới"
WELCOME_HTML = """
  <p>Xin chào! Tôi là trợ lý tư vấn <strong>Luật Lao động Việt Nam</strong>.</p>
  <p>Tôi có thể hỗ trợ bạn tra cứu Bộ luật Lao động 2019 và các Nghị định hướng dẫn.</p>
  <ul>
    <li>Quyền và nghĩa vụ của người lao động</li>
    <li>Hợp đồng lao động, thử việc, chấm dứt HĐLĐ</li>
    <li>Lương, BHXH, thời giờ làm việc, nghỉ phép</li>
  </ul>
"""


def storage_dir() -> str:
    return str(LEGALAI_DIR)


def _ensure_dirs() -> None:
    LEGALAI_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", session_id)
    if not cleaned:
        raise ValueError("session id không hợp lệ")
    return cleaned


def _session_path(session_id: str) -> Path:
    return CHAT_SESSIONS_DIR / f"{_safe_session_id(session_id)}.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".json",
        prefix=f"{path.stem}-",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(serialized)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        Path(tmp_path).replace(path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _default_welcome_messages() -> list[dict[str, Any]]:
    return [
        {
            "role": "bot",
            "html": WELCOME_HTML,
            "plain": "Xin chào!",
            "timestamp": int(time.time() * 1000),
        }
    ]


def _default_index() -> dict[str, Any]:
    return {"version": 2, "activeSessionId": "", "sessions": []}


def _load_index() -> dict[str, Any]:
    _ensure_dirs()
    if not CHAT_INDEX_PATH.exists():
        return _default_index()

    try:
        data = json.loads(CHAT_INDEX_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid index root")
        sessions = data.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        active = data.get("activeSessionId", "")
        if not isinstance(active, str):
            active = ""
        return {
            "version": 2,
            "activeSessionId": active,
            "sessions": sessions,
        }
    except Exception as exc:
        logger.warning("Không đọc được %s: %s", CHAT_INDEX_PATH, exc)
        return _default_index()


def _save_index(index: dict[str, Any]) -> None:
    _write_json_atomic(CHAT_INDEX_PATH, index)


def _load_session_messages(session_id: str) -> list[dict[str, Any]]:
    path = _session_path(session_id)
    if not path.exists():
        return _default_welcome_messages()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = data.get("messages")
        if isinstance(messages, list) and messages:
            return messages
    except Exception as exc:
        logger.warning("Không đọc được session %s: %s", session_id, exc)
    return _default_welcome_messages()


def _save_session_messages(session_id: str, messages: list[dict[str, Any]]) -> None:
    _write_json_atomic(_session_path(session_id), {"messages": messages})


def _migrate_legacy_monolithic() -> bool:
    """Tách chat-history.json cũ thành từng file session."""
    if not CHAT_HISTORY_LEGACY_PATH.exists() or CHAT_INDEX_PATH.exists():
        return False

    try:
        data = json.loads(CHAT_HISTORY_LEGACY_PATH.read_text(encoding="utf-8"))
        sessions = data.get("sessions", [])
        if not isinstance(sessions, list):
            sessions = []
        active = data.get("activeSessionId", "")
        if not isinstance(active, str):
            active = ""

        summaries: list[dict[str, Any]] = []
        for raw in sessions:
            if not isinstance(raw, dict):
                continue
            sid = str(raw.get("id", "")).strip()
            if not sid:
                continue
            sid = _safe_session_id(sid)
            messages = raw.get("messages")
            if not isinstance(messages, list):
                messages = _default_welcome_messages()
            _save_session_messages(sid, messages)
            summaries.append(
                {
                    "id": sid,
                    "title": str(raw.get("title") or DEFAULT_NEW_CHAT_TITLE),
                    "createdAt": int(raw.get("createdAt") or time.time() * 1000),
                    "updatedAt": int(raw.get("updatedAt") or time.time() * 1000),
                }
            )

        if summaries and active not in {s["id"] for s in summaries}:
            active = summaries[0]["id"]

        _save_index(
            {
                "version": 2,
                "activeSessionId": active,
                "sessions": summaries,
            }
        )
        backup = CHAT_HISTORY_LEGACY_PATH.with_suffix(".json.bak")
        CHAT_HISTORY_LEGACY_PATH.replace(backup)
        logger.info("Đã migrate %d session từ chat-history.json", len(summaries))
        return True
    except Exception as exc:
        logger.warning("Migrate chat-history.json thất bại: %s", exc)
        return False


def _ensure_initialized() -> dict[str, Any]:
    _ensure_dirs()
    _migrate_legacy_monolithic()
    index = _load_index()
    if index["sessions"]:
        return index

    now = int(time.time() * 1000)
    session_id = str(now)
    summary = {
        "id": session_id,
        "title": DEFAULT_NEW_CHAT_TITLE,
        "createdAt": now,
        "updatedAt": now,
    }
    _save_session_messages(session_id, _default_welcome_messages())
    index = {
        "version": 2,
        "activeSessionId": session_id,
        "sessions": [summary],
    }
    _save_index(index)
    return index


def list_session_summaries() -> dict[str, Any]:
    index = _ensure_initialized()
    return {
        "sessions": index["sessions"],
        "activeSessionId": index["activeSessionId"],
        "storagePath": storage_dir(),
    }


def get_session(session_id: str) -> dict[str, Any] | None:
    index = _ensure_initialized()
    summary = next(
        (s for s in index["sessions"] if s.get("id") == session_id),
        None,
    )
    if summary is None:
        return None

    return {
        **summary,
        "messages": _load_session_messages(session_id),
    }


def create_session(
    *,
    session_id: str | None = None,
    title: str = DEFAULT_NEW_CHAT_TITLE,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    index = _ensure_initialized()
    now = int(time.time() * 1000)
    sid = _safe_session_id(session_id or str(now))
    msgs = messages if messages is not None else _default_welcome_messages()

    summary = {
        "id": sid,
        "title": title,
        "createdAt": now,
        "updatedAt": now,
    }
    _save_session_messages(sid, msgs)
    index["sessions"] = [summary, *index["sessions"]]
    index["activeSessionId"] = sid
    _save_index(index)

    return {**summary, "messages": msgs}


def update_session(
    session_id: str,
    *,
    title: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    index = _ensure_initialized()
    found = False
    now = int(time.time() * 1000)
    updated_summary: dict[str, Any] | None = None

    for item in index["sessions"]:
        if item.get("id") != session_id:
            continue
        found = True
        if title is not None:
            item["title"] = title
        item["updatedAt"] = now
        updated_summary = dict(item)
        break

    if not found:
        return None

    if messages is not None:
        _save_session_messages(session_id, messages)

    _save_index(index)
    loaded_messages = (
        messages if messages is not None else _load_session_messages(session_id)
    )
    return {**updated_summary, "messages": loaded_messages}


def set_active_session(session_id: str) -> bool:
    index = _ensure_initialized()
    if not any(s.get("id") == session_id for s in index["sessions"]):
        return False
    index["activeSessionId"] = session_id
    _save_index(index)
    return True


def delete_session(session_id: str) -> bool:
    index = _ensure_initialized()
    before = len(index["sessions"])
    index["sessions"] = [s for s in index["sessions"] if s.get("id") != session_id]
    if len(index["sessions"]) == before:
        return False

    path = _session_path(session_id)
    if path.exists():
        path.unlink()

    if index["activeSessionId"] == session_id:
        index["activeSessionId"] = (
            index["sessions"][0]["id"] if index["sessions"] else ""
        )

    _save_index(index)
    return True

# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Tách điều khoản bằng LLM."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from contract_analysis.prompts import (
    CLAUSE_SEGMENTATION_INSTRUCTION,
    CLAUSE_SEGMENTATION_SYSTEM,
)
from contract_analysis.schema import Clause, ContractDocument

if TYPE_CHECKING:
    from graphrag_llm.completion.completion import LLMCompletion


MAX_CHARS_SEGMENT = 40000


def _coerce_categories(raw_categories, primary: str) -> list[str]:
    """LLM có thể trả ``categories`` dạng list, comma-string, hoặc null."""
    out: list[str] = []
    if isinstance(raw_categories, list):
        out = [str(x).strip() for x in raw_categories if str(x).strip()]
    elif isinstance(raw_categories, str) and raw_categories.strip():
        out = [s.strip() for s in re.split(r"[,;|]", raw_categories) if s.strip()]
    primary = (primary or "").strip()
    if primary and primary.upper() not in {c.upper() for c in out}:
        out.append(primary)
    return out


async def segment_clauses(llm: "LLMCompletion", doc: ContractDocument) -> list[Clause]:
    """Chạy prompt phân đoạn; fallback một điều khoản UNKNOWN nếu lỗi."""
    text = doc.raw_text[:MAX_CHARS_SEGMENT]
    user = CLAUSE_SEGMENTATION_INSTRUCTION + text
    from contract_analysis.llm_utils import llm_chat_json

    try:
        data = await llm_chat_json(llm, CLAUSE_SEGMENTATION_SYSTEM, user)
        if not isinstance(data, list):
            data = data.get("clauses", []) if isinstance(data, dict) else []
        clauses: list[Clause] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            cid = str(item.get("clause_id") or f"clause_{i + 1:03d}")
            primary = str(item.get("category") or "UNKNOWN")
            cats = _coerce_categories(item.get("categories"), primary)
            clauses.append(
                Clause(
                    clause_id=cid,
                    title=str(item.get("title") or ""),
                    category=primary,
                    categories=cats,
                    original_text=str(item.get("original_text") or ""),
                    summary=str(item.get("summary") or ""),
                    article_number=item.get("article_number"),
                )
            )
        if clauses:
            return clauses
    except Exception:
        pass

    return [
        Clause(
            clause_id=f"clause_{uuid.uuid4().hex[:8]}",
            title="Toàn bộ văn bản",
            category="UNKNOWN",
            categories=["UNKNOWN"],
            original_text=doc.raw_text[:12000],
            summary="Không tách được điều khoản tự động; dùng nguyên khối.",
            article_number=None,
        )
    ]


# Mẫu nhận diện category bắt buộc trực tiếp từ raw_text (backfill khi LLM gán
# 1 ``category`` cho 1 Điều chứa nhiều nội dung pháp lý).
_HEURISTIC_PATTERNS: dict[str, list[str]] = {
    "PARTY_INFO": [
        r"bên\s*a\b",
        r"bên\s*b\b",
        r"người\s+sử\s+dụng\s+lao\s+động",
        r"người\s+lao\s+động",
    ],
    "JOB_DESCRIPTION": [
        r"công\s+việc\s+phải\s+làm",
        r"chức\s+danh\s+chuyên\s+môn",
        r"vị\s+trí\s+công\s+tác",
        r"nhiệm\s+vụ",
    ],
    "WORKPLACE": [
        r"địa\s+điểm\s+làm\s+việc",
        r"nơi\s+làm\s+việc",
    ],
    "CONTRACT_TYPE": [
        r"loại\s+hợp\s+đồng",
        r"hợp\s+đồng\s+(không\s+)?xác\s+định\s+thời\s+hạn",
        r"hợp\s+đồng\s+thời\s+vụ",
        r"ký\s+lần\s+thứ",
    ],
    "CONTRACT_DURATION": [
        r"thời\s+hạn\s+(của\s+)?hợp\s+đồng",
        r"từ\s+ngày[^.]{0,80}đến\s+ngày",
        r"có\s+hiệu\s+lực\s+kể\s+từ\s+ngày",
    ],
    "WORKING_HOURS": [
        r"thời\s+giờ\s+làm\s+việc",
        r"giờ\s+làm\s+việc",
        r"\d+\s*giờ\s*/\s*(ngày|tuần)",
        r"nghỉ\s+hàng\s+tuần",
    ],
    "SALARY": [
        r"mức\s+lương",
        r"lương\s+căn\s+bản",
        r"hình\s+thức\s+trả\s+lương",
        r"\d[\d.,]*\s*(đồng|vnđ|vnd)\s*/\s*tháng",
    ],
    "SOCIAL_INSURANCE": [
        r"\bbhxh\b",
        r"\bbhyt\b",
        r"\bbhtn\b",
        r"bảo\s+hiểm\s+xã\s+hội",
        r"bảo\s+hiểm\s+y\s+tế",
        r"bảo\s+hiểm\s+thất\s+nghiệp",
    ],
    "TRAINING": [
        r"đào\s+tạo",
        r"bồi\s+dưỡng",
        r"huấn\s+luyện",
        r"nâng\s+cao\s+(kỹ\s+năng|trình\s+độ)",
    ],
}


def infer_categories_from_text(text: str) -> set[str]:
    """Quét regex nhanh để phát hiện sự có mặt của các mandatory category."""
    if not text:
        return set()
    low = text.lower()
    found: set[str] = set()
    for cat, patterns in _HEURISTIC_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, low):
                found.add(cat)
                break
    return found


def compute_missing_mandatory(
    clauses: list[Clause],
    *,
    raw_text: str | None = None,
) -> list[str]:
    """Tính category bắt buộc còn thiếu.

    1) Dùng nhãn LLM trả về: ``category`` + ``categories`` (đa nhãn).
    2) Backfill bằng heuristic regex trên ``raw_text`` để tránh báo "thiếu giả"
       khi một ``Điều`` gộp nhiều nội dung mà LLM chỉ gán 1 nhãn.
    """
    from contract_analysis.constants import MANDATORY_CLAUSE_KEYS

    found: set[str] = set()
    for c in clauses:
        found.update(c.effective_categories())
    if raw_text:
        found.update(infer_categories_from_text(raw_text))
    return sorted(k for k in MANDATORY_CLAUSE_KEYS if k not in found)

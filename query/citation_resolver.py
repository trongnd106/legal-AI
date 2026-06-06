"""
query/citation_resolver.py — Parse và resolve [Data: ...] citations từ GraphRAG.

GraphRAG yêu cầu LLM gắn trích dẫn dạng:
  [Data: Sources (40)]
  [Data: Entities (3633); Relationships (5425, 5433); Sources (422)]

Các số trong ngoặc là human_readable_id (short_id) của bản ghi trong context.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

DATA_CITATION_PATTERN = re.compile(r"\[Data:\s*([^\]]+)\]")
GROUP_PATTERN = re.compile(r"(\w+)\s*\(([^)]+)\)")

TYPE_LABELS_VI: dict[str, str] = {
    "Sources": "Nguồn văn bản",
    "Documents": "Nguồn văn bản",
    "Entities": "Thực thể",
    "Relationships": "Quan hệ",
    "Reports": "Báo cáo",
    "Claims": "Khẳng định",
}

TYPE_ICONS: dict[str, str] = {
    "Sources": "📄",
    "Documents": "📄",
    "Entities": "🏷️",
    "Relationships": "🔗",
    "Reports": "📋",
    "Claims": "✓",
}

CONTEXT_KEY_MAP: dict[str, str] = {
    "sources": "sources",
    "documents": "sources",
    "entities": "entities",
    "relationships": "relationships",
    "reports": "reports",
    "claims": "claims",
}


def _truncate(text: str, max_len: int = 280) -> str:
    text = " ".join(str(text).split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _lookup_record(
    context_data: dict[str, Any],
    cite_type: str,
    record_id: str,
) -> dict[str, str] | None:
    """Tra cứu bản ghi theo type + id trong context_data."""
    ctx_key = CONTEXT_KEY_MAP.get(cite_type.lower())
    if not ctx_key:
        return None

    table = context_data.get(ctx_key)
    if table is None or not isinstance(table, pd.DataFrame) or table.empty:
        return None
    if "id" not in table.columns:
        return None

    rid = str(record_id).strip()
    matched = table[table["id"].astype(str).str.strip() == rid]
    if matched.empty:
        return None

    row = matched.iloc[0]
    label, detail = _format_record(cite_type, row)
    return {
        "type": cite_type,
        "id": rid,
        "label": label,
        "detail": detail,
    }


def _format_record(cite_type: str, row: pd.Series) -> tuple[str, str]:
    """Tạo label ngắn và mô tả chi tiết cho tooltip."""
    if cite_type in ("Sources", "Documents"):
        text = str(row.get("text", "") or "")
        label = _extract_article_label(text) or f"Nguồn #{row.get('id', '')}"
        return label, _truncate(text, 400)

    if cite_type == "Entities":
        title = str(row.get("entity", row.get("title", "")) or f"Thực thể #{row.get('id', '')}")
        desc = str(row.get("description", "") or "")
        return title, _truncate(desc or title, 400)

    if cite_type == "Relationships":
        src = str(row.get("source", "") or "")
        tgt = str(row.get("target", "") or "")
        desc = str(row.get("description", "") or "")
        label = f"{src} → {tgt}" if src and tgt else f"Quan hệ #{row.get('id', '')}"
        return _truncate(label, 80), _truncate(desc or label, 400)

    if cite_type == "Reports":
        title = str(row.get("title", "") or f"Báo cáo #{row.get('id', '')}")
        summary = str(row.get("summary", row.get("content", "")) or "")
        return _truncate(title, 80), _truncate(summary or title, 400)

    if cite_type == "Claims":
        subject = str(row.get("subject", row.get("subject_id", "")) or "")
        status = str(row.get("status", "") or "")
        desc = str(row.get("description", row.get("claim", "")) or "")
        label = subject or f"Khẳng định #{row.get('id', '')}"
        detail = f"{desc} (Trạng thái: {status})" if status else desc
        return _truncate(label, 80), _truncate(detail or label, 400)

    return f"{cite_type} #{row.get('id', '')}", str(row.to_dict())


def _extract_article_label(text: str) -> str | None:
    """Trích nhãn Điều/Khoản từ nội dung nguồn nếu có."""
    for pattern in (
        r"Điều\s+\d+",
        r"Khoản\s+\d+\s+Điều\s+\d+",
        r"Điểm\s+[a-zđ]\s+Khoản\s+\d+\s+Điều\s+\d+",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0)
    first_line = text.strip().split("\n", 1)[0].strip()
    if first_line:
        return _truncate(first_line, 60)
    return None


def parse_data_citation_groups(raw: str) -> list[tuple[str, list[str]]]:
    """
    Parse nội dung trong [Data: ...].
    Ví dụ: "Entities (3633); Relationships (5425, 5433); Sources (422)"
    → [("Entities", ["3633"]), ("Relationships", ["5425", "5433"]), ("Sources", ["422"])]
    """
    groups: list[tuple[str, list[str]]] = []
    for m in GROUP_PATTERN.finditer(raw):
        cite_type = m.group(1).strip()
        ids_raw = m.group(2)
        ids = [
            part.strip()
            for part in ids_raw.split(",")
            if part.strip() and part.strip().lower() != "+more"
        ]
        if ids:
            groups.append((cite_type, ids))
    return groups


def resolve_data_citations(
    answer: str,
    context_data: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """
    Trích xuất và resolve tất cả [Data: ...] trong câu trả lời.

    Returns list of dicts: {key, type, id, label, detail, icon, type_label}
    """
    if not answer or not context_data:
        return []

    seen: set[str] = set()
    results: list[dict[str, str]] = []

    for block in DATA_CITATION_PATTERN.findall(answer):
        for cite_type, ids in parse_data_citation_groups(block):
            for record_id in ids:
                key = f"{cite_type}:{record_id}"
                if key in seen:
                    continue
                seen.add(key)

                resolved = _lookup_record(context_data, cite_type, record_id)
                if resolved:
                    label = resolved["label"]
                    detail = resolved["detail"]
                else:
                    type_label = TYPE_LABELS_VI.get(cite_type, cite_type)
                    label = f"{type_label} #{record_id}"
                    detail = f"Không tìm thấy chi tiết cho {type_label} #{record_id} trong ngữ cảnh truy vấn."

                results.append({
                    "key": key,
                    "type": cite_type,
                    "id": record_id,
                    "label": label,
                    "detail": detail,
                    "icon": TYPE_ICONS.get(cite_type, "📎"),
                    "type_label": TYPE_LABELS_VI.get(cite_type, cite_type),
                })

    return results

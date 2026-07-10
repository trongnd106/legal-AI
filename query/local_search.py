"""
query/local_search.py — Local Search sử dụng graphrag.api.

Local search phù hợp cho câu hỏi cụ thể về Điều/Khoản hoặc về một thực thể pháp lý
(ví dụ: "Điều kiện để đơn phương chấm dứt hợp đồng lao động là gì?").
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from graphrag.api.query import local_search, local_search_streaming
from graphrag.callbacks.noop_query_callbacks import NoopQueryCallbacks

from query.loader import GraphLoader


async def ask_local(
    question: str,
    loader: GraphLoader,
    community_level: int = 2,
    response_type: str = "single paragraph",
) -> dict:
    """
    Local search — tìm kiếm có chiều sâu về một Điều/Khoản hoặc chủ đề cụ thể.

    Parameters
    ----------
    question:
        Câu hỏi pháp lý cụ thể.
    loader:
        GraphLoader đã gọi .load().
    community_level:
        Cấp community để filter context.
    response_type:
        "single paragraph" | "multiple paragraphs" | "single sentence" | v.v.

    Returns
    -------
    dict với các key:
        answer            : str — câu trả lời
        context_data      : dict[str, pd.DataFrame] — dữ liệu context thô
        article_citations : list[str] — số Điều/Khoản được nhắc đến trong câu trả lời
        entities_used     : list[str] — title của các entities được sử dụng
    """
    response, context_data = await local_search(
        config=loader.config,
        entities=loader.entities,
        communities=loader.communities,
        community_reports=loader.community_reports,
        text_units=loader.text_units,
        relationships=loader.relationships,
        covariates=loader.covariates,
        community_level=community_level,
        response_type=response_type,
        query=question,
    )

    # context_data là dict[str, pd.DataFrame]; trích xuất citation từ câu trả lời
    article_citations = _extract_citations(str(response))
    entities_used     = _collect_entity_titles(context_data)

    return {
        "answer":             response,
        "context_data":       context_data,
        "article_citations":  article_citations,
        "entities_used":      entities_used,
    }


def _extract_citations(text: str) -> list[str]:
    """Trích xuất số Điều/Khoản/Điểm và các văn bản pháp lý được nhắc đến."""
    citations: set[str] = set()
    # Điều, Khoản, Điểm
    for m in re.finditer(
        r"(?:Điều\s+\d+|Khoản\s+\d+\s+Điều\s+\d+|Điểm\s+[a-zđ]\s+Khoản\s+\d+\s+Điều\s+\d+)",
        text, re.IGNORECASE,
    ):
        citations.add(m.group(0))
    # Nghị định
    for m in re.finditer(r"Nghị\s+định\s+(?:số\s+)?(\d+/\d+)", text, re.IGNORECASE):
        citations.add(f"NĐ {m.group(1)}")
    # Thông tư
    for m in re.finditer(r"Thông\s+tư\s+(?:số\s+)?(\d+/\d+)", text, re.IGNORECASE):
        citations.add(f"TT {m.group(1)}")
    # Bộ luật Lao động
    for m in re.finditer(r"Bộ\s+luật\s+Lao\s+động(?:\s+năm\s+(\d+))?", text, re.IGNORECASE):
        citations.add("Bộ luật Lao động")
        if m.group(1):
            citations.add(f"BLLĐ {m.group(1)}")
    if re.search(r"\bBLLĐ\s+\d{4}\b", text, re.IGNORECASE):
        for m in re.finditer(r"\bBLLĐ\s+(\d{4})\b", text, re.IGNORECASE):
            citations.add(f"BLLĐ {m.group(1)}")
    # Bộ luật Dân sự, Hình sự
    for name, short in [("Dân sự", "Bộ luật Dân sự"), ("Hình sự", "BLHS")]:
        if re.search(rf"Bộ\s+luật\s+{re.escape(name)}", text, re.IGNORECASE):
            citations.add(short)
    # Luật
    law_map = [
        ("Bảo hiểm xã hội", "Luật BHXH"),
        ("Doanh nghiệp", "Luật Doanh nghiệp"),
        ("Đầu tư", "Luật Đầu tư"),
        ("Giao thông", "Luật Giao thông"),
        ("Đất đai", "Luật Đất đai"),
        ("Thương mại", "Luật Thương mại"),
        ("Phá sản", "Luật Phá sản"),
        ("Việc làm", "Luật Việc làm"),
    ]
    for full_name, short in law_map:
        if re.search(rf"Luật\s+{re.escape(full_name)}", text, re.IGNORECASE):
            citations.add(short)
    # Phụ lục, Ghi chú
    if re.search(r"Phụ\s+lục", text, re.IGNORECASE):
        citations.add("Phụ lục")
    if re.search(r"Ghi\s+chú", text, re.IGNORECASE):
        citations.add("Ghi chú")
    return sorted(citations)


def _collect_entity_titles(context_data: dict) -> list[str]:
    """
    Trích xuất danh sách title entities từ context_data.
    context_data có thể là dict[str, pd.DataFrame] hoặc str/list tuỳ GraphRAG version.
    """
    import pandas as pd

    titles: list[str] = []
    if not isinstance(context_data, dict):
        return titles

    for key, value in context_data.items():
        if isinstance(value, pd.DataFrame) and "title" in value.columns:
            titles.extend(value["title"].dropna().tolist())

    return list(dict.fromkeys(titles))   # preserve order, deduplicate


async def ask_local_streaming(
    question: str,
    loader: GraphLoader,
    community_level: int = 2,
    response_type: str = "single paragraph",
) -> AsyncGenerator[str | dict[str, Any], None]:
    """
    Local search streaming — yield tokens khi LLM trả về từng chunk,
    sau đó yield một dict chứa kết quả cuối cùng (citations, entities, ...).
    """
    context_data: dict[str, Any] = {}

    def on_context(ctx: Any) -> None:
        nonlocal context_data
        context_data = ctx

    callbacks = [NoopQueryCallbacks()]
    callbacks[0].on_context = on_context

    full_response = ""
    async for chunk in local_search_streaming(
        config=loader.config,
        entities=loader.entities,
        communities=loader.communities,
        community_reports=loader.community_reports,
        text_units=loader.text_units,
        relationships=loader.relationships,
        covariates=loader.covariates,
        community_level=community_level,
        response_type=response_type,
        query=question,
        callbacks=callbacks,
    ):
        full_response += chunk
        yield chunk

    article_citations = _extract_citations(full_response)
    entities_used = _collect_entity_titles(context_data)

    yield {
        "type": "done",
        "answer": full_response,
        "article_citations": article_citations,
        "entities_used": entities_used,
        "context_data": context_data,
    }


# ---------------------------------------------------------------------------
# Ví dụ chạy CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else "data/labor-law"
    q    = sys.argv[2] if len(sys.argv) > 2 else (
        "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động trong trường hợp nào?"
    )

    loader = GraphLoader(root).load()
    result = asyncio.run(ask_local(q, loader))

    print("\n=== CÂU TRẢ LỜI ===")
    print(result["answer"])
    if result["article_citations"]:
        print("\n=== TRÍCH DẪN ===")
        for c in result["article_citations"]:
            print(f"  {c}")
    if result["entities_used"]:
        print("\n=== THỰC THỂ SỬ DỤNG ===")
        for e in result["entities_used"][:10]:
            print(f"  {e}")

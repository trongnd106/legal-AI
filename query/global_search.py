"""
query/global_search.py — Global Search sử dụng graphrag.api.

Global search phù hợp cho câu hỏi tổng quát cần tổng hợp toàn bộ hệ thống pháp luật
(ví dụ: "Những nguyên tắc cơ bản của luật lao động Việt Nam là gì?").
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from graphrag.api.query import global_search, global_search_streaming
from graphrag.callbacks.noop_query_callbacks import NoopQueryCallbacks

from query.loader import GraphLoader

DOMAIN_LABELS: dict[str, str] = {
    "lao_dong":     "luật lao động, quan hệ lao động, hợp đồng lao động",
    "dan_su":       "luật dân sự, giao dịch dân sự, hợp đồng dân sự",
    "hinh_su":      "luật hình sự, tội phạm, hình phạt",
    "doanh_nghiep": "luật doanh nghiệp, công ty, cổ đông",
    "dat_dai":      "luật đất đai, quyền sử dụng đất, đất ở",
}


async def ask_global(
    question: str,
    loader: GraphLoader,
    domain_filter: str | None = None,
    community_level: int | None = 2,
    dynamic_community_selection: bool = False,
    response_type: str = "multiple paragraphs",
) -> dict:
    """
    Global search trên toàn bộ hệ thống pháp luật VN.

    Parameters
    ----------
    question:
        Câu hỏi pháp lý cần trả lời.
    loader:
        GraphLoader đã gọi .load().
    domain_filter:
        Giới hạn phạm vi ("lao_dong", "dan_su", "hinh_su", "doanh_nghiep", "dat_dai"),
        hoặc None để tìm toàn hệ thống.
    community_level:
        Cấp độ community để tìm kiếm (None = dùng tất cả).
    dynamic_community_selection:
        Nếu True, GraphRAG tự chọn community level tối ưu.
    response_type:
        "multiple paragraphs" | "single paragraph" | "single sentence" | v.v.

    Returns
    -------
    dict với các key:
        answer          : str — câu trả lời tổng hợp
        domain_filter   : str | None
        context_data    : dict[str, pd.DataFrame] — dữ liệu context thô từ GraphRAG
        article_citations: list[str] — số Điều được trích dẫn trong câu trả lời
    """
    # Bổ sung context domain vào query để community routing chính xác hơn
    query = question
    if domain_filter:
        domain_ctx = DOMAIN_LABELS.get(domain_filter, "")
        if domain_ctx:
            query = f"[Lĩnh vực: {domain_ctx}] {question}"

    response, context_data = await global_search(
        config=loader.config,
        entities=loader.entities,
        communities=loader.communities,
        community_reports=loader.community_reports,
        community_level=community_level,
        dynamic_community_selection=dynamic_community_selection,
        response_type=response_type,
        query=query,
    )

    return {
        "answer":           response,
        "domain_filter":    domain_filter,
        "context_data":     context_data,
        "article_citations": _extract_citations(str(response)),
    }


def _extract_citations(text: str) -> list[str]:
    """Trích xuất số Điều/Khoản và các văn bản pháp lý được nhắc đến."""
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


async def ask_global_streaming(
    question: str,
    loader: GraphLoader,
    domain_filter: str | None = None,
    community_level: int | None = 2,
    dynamic_community_selection: bool = False,
    response_type: str = "multiple paragraphs",
) -> AsyncGenerator[str | dict[str, Any], None]:
    """
    Global search streaming — yield tokens khi LLM trả về từng chunk,
    sau đó yield một dict chứa kết quả cuối cùng (citations, ...).
    """
    query = question
    if domain_filter:
        domain_ctx = DOMAIN_LABELS.get(domain_filter, "")
        if domain_ctx:
            query = f"[Lĩnh vực: {domain_ctx}] {question}"

    context_data: dict[str, Any] = {}

    def on_context(ctx: Any) -> None:
        nonlocal context_data
        context_data = ctx

    callbacks = [NoopQueryCallbacks()]
    callbacks[0].on_context = on_context

    full_response = ""
    async for chunk in global_search_streaming(
        config=loader.config,
        entities=loader.entities,
        communities=loader.communities,
        community_reports=loader.community_reports,
        community_level=community_level,
        dynamic_community_selection=dynamic_community_selection,
        response_type=response_type,
        query=query,
        callbacks=callbacks,
    ):
        full_response += chunk
        yield chunk

    article_citations = _extract_citations(full_response)

    yield {
        "type": "done",
        "answer": full_response,
        "article_citations": article_citations,
        "context_data": context_data,
    }


# ---------------------------------------------------------------------------
# Ví dụ chạy CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else "data/labor-law"
    q    = sys.argv[2] if len(sys.argv) > 2 else "Những nguyên tắc cơ bản của quan hệ lao động là gì?"
    domain = sys.argv[3] if len(sys.argv) > 3 else None

    loader = GraphLoader(root).load()
    result = asyncio.run(ask_global(q, loader, domain_filter=domain))

    print("\n=== CÂU TRẢ LỜI ===")
    print(result["answer"])
    if result["article_citations"]:
        print("\n=== TRÍCH DẪN PHÁT HIỆN ===")
        for c in result["article_citations"]:
            print(f"  {c}")

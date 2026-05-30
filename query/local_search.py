"""
query/local_search.py — Local Search sử dụng graphrag.api.

Local search phù hợp cho câu hỏi cụ thể về Điều/Khoản hoặc về một thực thể pháp lý
(ví dụ: "Điều kiện để đơn phương chấm dứt hợp đồng lao động là gì?").
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from graphrag.api.query import local_search

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
    """Trích xuất số Điều/Khoản/Điểm được dùng trong câu trả lời."""
    citations: set[str] = set()
    for m in re.finditer(
        r"(?:Điều\s+\d+|Khoản\s+\d+\s+Điều\s+\d+|Điểm\s+[a-zđ]\s+Khoản\s+\d+\s+Điều\s+\d+)",
        text,
        re.IGNORECASE,
    ):
        citations.add(m.group(0))
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

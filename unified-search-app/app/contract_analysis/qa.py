# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Q&A trên hợp đồng đã phân tích (GraphRAG + LLM)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import graphrag.api as api
import pandas as pd

from contract_analysis.llm_utils import get_completion_for_contract_tasks
from contract_analysis.prompts import QA_SYSTEM, QA_USER_TEMPLATE
from contract_analysis.schema import Clause, ContractAnalysisResult

if TYPE_CHECKING:
    from graphrag.config.models.graph_rag_config import GraphRagConfig


def _pick_relevant_clauses(question: str, clauses: list[Clause], *, limit: int = 6) -> list[Clause]:
    q = question.lower()
    scored: list[tuple[int, Clause]] = []
    for c in clauses:
        blob = f"{c.title} {c.summary} {c.category} {c.original_text[:500]}".lower()
        score = sum(1 for tok in q.split() if len(tok) > 2 and tok in blob)
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for s, c in scored[:limit] if s > 0] or clauses[:limit]


async def answer_contract_question(
    *,
    config: "GraphRagConfig",
    text_units: pd.DataFrame,
    analysis: ContractAnalysisResult,
    question: str,
) -> str:
    """Trả lời câu hỏi với ngữ cảnh điều khoản + basic_search pháp luật."""
    relevant = _pick_relevant_clauses(question, analysis.clauses)
    clauses_blob = json.dumps(
        [
            {
                "id": c.clause_id,
                "category": c.category,
                "title": c.title,
                "summary": c.summary,
                "excerpt": c.original_text[:1200],
            }
            for c in relevant
        ],
        ensure_ascii=False,
        indent=2,
    )

    legal_context = ""
    if text_units is not None and not text_units.empty:
        try:
            lc, _ = await api.basic_search(
                config=config,
                text_units=text_units,
                response_type="Multiple Paragraphs",
                query=f"{question} — luật lao động Việt Nam",
            )
            legal_context = lc if isinstance(lc, str) else str(lc)
        except Exception as exc:
            legal_context = f"(Không truy xuất GraphRAG: {exc})"

    excerpt = analysis.contract.raw_text[:6000]
    summary_tail = analysis.markdown_report[:4000]

    llm = get_completion_for_contract_tasks(config)
    user = QA_USER_TEMPLATE.format(
        contract_excerpt=excerpt,
        relevant_clauses=clauses_blob,
        legal_context=legal_context[:12000],
        analysis_summary=summary_tail,
        question=question,
    )
    resp = await llm.completion_async(
        messages=[
            {"role": "system", "content": QA_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_completion_tokens=4096,
    )
    return resp.content.strip()

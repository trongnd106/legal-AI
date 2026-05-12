# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Phân tích sâu bằng LLM (batch) trên ngữ cảnh GraphRAG."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal, cast

from contract_analysis.constants import REGIONAL_MINIMUM_WAGE
from contract_analysis.prompts import VIOLATION_BATCH_INSTRUCTION, VIOLATION_BATCH_SYSTEM
from contract_analysis.schema import Clause, ContractIssue, MappedLawSnippet

if TYPE_CHECKING:
    from graphrag_llm.completion.completion import LLMCompletion

Severity = Literal[
    "VIOLATION",
    "HIGH_RISK",
    "MEDIUM_RISK",
    "COMPLIANT",
    "NOT_COVERED",
]

_ALLOWED_SEVERITY = frozenset({
    "VIOLATION",
    "HIGH_RISK",
    "MEDIUM_RISK",
    "COMPLIANT",
    "NOT_COVERED",
})


def _normalize_severity(raw: str) -> Severity:
    return cast(Severity, raw if raw in _ALLOWED_SEVERITY else "NOT_COVERED")


def _issues_from_llm_item(
    clause_id: str,
    payload: dict[str, Any],
) -> list[ContractIssue]:
    sev = _normalize_severity(str(payload.get("severity") or "NOT_COVERED"))
    out: list[ContractIssue] = []
    for i, it in enumerate(payload.get("issues") or []):
        if not isinstance(it, dict):
            continue
        out.append(
            ContractIssue(
                issue_id=str(it.get("issue_id") or f"L{i + 1}"),
                description=str(it.get("description") or ""),
                severity=sev,
                legal_basis=str(it.get("legal_basis") or ""),
                recommendation=str(it.get("recommendation") or ""),
                affected_party=str(it.get("affected_party") or ""),
                clause_id=clause_id,
            )
        )
    return out


async def llm_clause_review_batch(
    llm: "LLMCompletion",
    clauses: list[Clause],
    mapped: dict[str, MappedLawSnippet],
    *,
    region: str,
) -> dict[str, list[ContractIssue]]:
    """Một lần gọi LLM cho toàn bộ điều khoản + ghép ngữ cảnh."""
    from contract_analysis.llm_utils import llm_chat_json

    slim_clauses = [
        {
            "clause_id": c.clause_id,
            "category": c.category,
            "title": c.title,
            "summary": c.summary,
            "original_text": (c.original_text[:2500] + "…")
            if len(c.original_text) > 2500
            else c.original_text,
        }
        for c in clauses
    ]
    legal_chunks = []
    for c in clauses:
        sn = mapped.get(c.clause_id)
        if sn:
            legal_chunks.append(f"--- {c.clause_id} ---\n{sn.rag_answer[:3500]}")
    legal_context = "\n\n".join(legal_chunks)[:32000]

    w = REGIONAL_MINIMUM_WAGE
    user = VIOLATION_BATCH_INSTRUCTION.format(
        clauses_json=json.dumps(slim_clauses, ensure_ascii=False),
        legal_context=legal_context,
        w1=w["I"],
        w2=w["II"],
        w3=w["III"],
        w4=w["IV"],
        region=region,
    )
    try:
        data = await llm_chat_json(llm, VIOLATION_BATCH_SYSTEM, user)
    except Exception:
        return {}

    results = data.get("results") if isinstance(data, dict) else data
    if not isinstance(results, list):
        return {}

    by_clause: dict[str, list[ContractIssue]] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("clause_id") or "")
        if not cid:
            continue
        by_clause[cid] = _issues_from_llm_item(cid, item)
    return by_clause

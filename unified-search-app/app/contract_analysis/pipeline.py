# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Orchestration pipeline — tối ưu tốc độ.

Chiến lược:
  1. Load doc (sync hoặc async OCR nếu cần)
  2. LLM segment — không thể song song với bước khác (cần đầu ra)
  3. apply_rules NGAY (sync, < 5ms/clause) — phân loại clause theo mức rủi ro
  4. map_all_clauses (concurrency=4) — CHỈ đối với clauses đáng map
  5. llm_review_batch — CHỈ với clauses COMPLEX (không có COMPLIANT rule clear)
  6. finalize_report, persist (async thread)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import uuid

import pandas as pd

from contract_analysis.detector import llm_clause_review_batch
from contract_analysis.llm_utils import get_completion_for_contract_tasks
from contract_analysis.loader import contract_document_from_text, load
from contract_analysis.mapper import map_all_clauses
from contract_analysis.neo4j_store import get_driver_from_env, persist_contract_analysis
from contract_analysis.reporter import finalize_report
from contract_analysis.rules import RuleContext, apply_rules
from contract_analysis.schema import (
    ClauseAnalysis,
    ContractAnalysisResult,
    ContractIssue,
    MappedLawSnippet,
)
from contract_analysis.segmenter import compute_missing_mandatory, segment_clauses

if TYPE_CHECKING:
    from graphrag.config.models.graph_rag_config import GraphRagConfig

logger = logging.getLogger(__name__)

# Các category thường chứa nội dung phức tạp → ưu tiên LLM review
_COMPLEX_CATEGORIES = frozenset({
    "SALARY",
    "WORKING_HOURS",
    "PROBATION",
    "TERMINATION",
    "SOCIAL_INSURANCE",
    "PENALTY_CLAUSE",
    "UNILATERAL_TERMS",
    "WAIVER_CLAUSE",
    "NON_COMPETE",
    "DISPUTE_RESOLUTION",
})

# Rule issues đủ nặng → đã có VIOLATION → không cần LLM review nữa cho category đó
_SKIP_LLM_IF_VIOLATION = frozenset({"VR001", "VR002", "VR003", "VR005", "VR006", "VR007"})


def _needs_llm_review(clause_analysis: ClauseAnalysis) -> bool:
    """
    Quyết định có cần gửi clause lên LLM không.

    - Nếu category thuộc nhóm phức tạp → có
    - Nếu đã có VIOLATION rule rõ ràng → không cần thêm LLM cho chi phí
      (LLM sẽ chỉ đồng ý, không thêm insight)
    - UNKNOWN luôn cần LLM vì rule không cover
    """
    c = clause_analysis.clause
    cats = c.effective_categories()

    if "UNKNOWN" in cats:
        return True
    if not (cats & _COMPLEX_CATEGORIES):
        return False

    # Nếu đã có VIOLATION từ rule rõ ràng trong nhóm skip → bỏ LLM
    rule_ids = {iss.issue_id for iss in clause_analysis.rule_issues}
    if rule_ids & _SKIP_LLM_IF_VIOLATION:
        return False

    return True


async def run_contract_analysis(
    *,
    config: "GraphRagConfig",
    text_units: pd.DataFrame,
    file_path: str | Path | None = None,
    raw_contract_text: str | None = None,
    filename: str = "contract.txt",
    wage_region: str = "IV",
    max_probation_days: int = 60,
    skip_llm_review: bool = False,
    skip_graph_mapping: bool = False,
    pdf_force_ocr: bool = False,
    pdf_detect_scan: bool = True,
    persist_neo4j: bool = True,
    entities: pd.DataFrame | None = None,
    relationships: pd.DataFrame | None = None,
    use_neo4j_knowledge_graph: bool = True,
    neo4j_graph_hops: int = 2,
    map_concurrency: int = 4,
) -> ContractAnalysisResult:
    """
    Chạy pipeline phân tích HĐLĐ — tối ưu tốc độ.

    Parameters
    ----------
    file_path:
        Đường dẫn PDF/DOCX/TXT.
    raw_contract_text:
        Ưu tiên khi có — nội dung đã đọc sẵn (upload Streamlit).
    wage_region:
        I–IV cho rule lương tối thiểu vùng.
    skip_graph_mapping:
        Bỏ basic_search (test nhanh).
    skip_llm_review:
        Bỏ toàn bộ LLM batch review (chỉ dùng rules).
    map_concurrency:
        Số clause map song song (default=4, tăng nếu rate limit OK).
    pdf_force_ocr:
        Luôn PaddleOCR cho PDF (scan).
    pdf_detect_scan:
        Nếu True, tự phát hiện PDF ít text layer → PaddleOCR.
    persist_neo4j:
        Ghi ``ContractSession`` khi có ``NEO4J_*`` trong môi trường / `.env`.
    entities, relationships:
        DataFrames từ workspace để seed Neo4j entity graph.
    use_neo4j_knowledge_graph:
        Mở rộng ``RELATED_TO`` trong Neo4j sau basic_search.
    neo4j_graph_hops:
        Độ sâu Cypher (1–3).
    """
    session_id = str(uuid.uuid4())

    # ── Bước 1: Load document ─────────────────────────────────────────────
    if raw_contract_text is not None:
        doc = contract_document_from_text(raw_contract_text, filename=filename)
    elif file_path is not None:
        doc = load(
            str(file_path),
            pdf_force_ocr=pdf_force_ocr,
            pdf_detect_scan=pdf_detect_scan,
        )
    else:
        msg = "Cần file_path hoặc raw_contract_text."
        raise ValueError(msg)

    llm = get_completion_for_contract_tasks(config)

    # ── Bước 2: Segment bằng LLM ─────────────────────────────────────────
    clauses = await segment_clauses(llm, doc)
    missing = compute_missing_mandatory(clauses, raw_text=doc.raw_text)

    # ── Bước 3: Apply rules NGAY (sync, ~0ms) ────────────────────────────
    rule_ctx = RuleContext(region=wage_region.upper(), max_probation_days=max_probation_days)
    pre_analyses: list[ClauseAnalysis] = [
        ClauseAnalysis(clause=c, rule_issues=apply_rules(c, rule_ctx))
        for c in clauses
    ]

    # ── Bước 4: Phân loại: cần map? cần LLM? ─────────────────────────────
    clauses_need_map: list = []
    clauses_need_llm: list = []
    for ca in pre_analyses:
        cats = ca.clause.effective_categories()
        if cats & _COMPLEX_CATEGORIES or "UNKNOWN" in cats:
            clauses_need_map.append(ca.clause)
        if not skip_llm_review and _needs_llm_review(ca):
            clauses_need_llm.append(ca.clause)

    logger.info(
        "Clauses total=%d, need_map=%d, need_llm=%d",
        len(clauses), len(clauses_need_map), len(clauses_need_llm),
    )

    # ── Bước 5: map_all_clauses + llm_review SONG SONG ───────────────────
    # Chạy map và LLM review đồng thời (2 coroutines độc lập)
    neo_driver = None
    mapped: dict[str, MappedLawSnippet] = {}
    llm_by_id: dict[str, list[ContractIssue]] = {}

    async def do_map() -> dict[str, MappedLawSnippet]:
        if skip_graph_mapping or text_units is None or text_units.empty:
            return {}
        if not clauses_need_map:
            return {}

        want_kg = bool(
            use_neo4j_knowledge_graph
            and entities is not None
            and not entities.empty,
        )
        nonlocal neo_driver
        if want_kg:
            neo_driver = get_driver_from_env()
            if neo_driver is None:
                logger.info("Knowledge Graph: không có Neo4j driver — bỏ mở rộng.")

        return await map_all_clauses(
            config,
            text_units,
            clauses_need_map,
            max_concurrent=map_concurrency,
            entities_df=entities if want_kg else None,
            relationships_df=relationships if want_kg else None,
            neo4j_driver=neo_driver,
            neo4j_max_hops=max(1, min(int(neo4j_graph_hops), 3)),
        )

    async def do_llm_review(
        _mapped: dict[str, MappedLawSnippet],
    ) -> dict[str, list[ContractIssue]]:
        if skip_llm_review or not clauses_need_llm:
            return {}
        # Truyền mapped (có thể rỗng nếu skip_graph_mapping) và
        # truyền thêm rule_issues vào prompt
        rule_issues_by_id = {ca.clause.clause_id: ca.rule_issues for ca in pre_analyses}
        return await llm_clause_review_batch(
            llm,
            clauses_need_llm,
            _mapped,
            region=wage_region.upper(),
            rule_issues_by_id=rule_issues_by_id,
        )

    try:
        # Bước 5a: map (cần kết quả trước LLM review để cho context tốt hơn)
        mapped = await do_map()
        # Bước 5b: LLM review (dùng mapped làm context)
        llm_by_id = await do_llm_review(mapped)
    finally:
        if neo_driver is not None:
            neo_driver.close()

    # ── Bước 6: Merge results ─────────────────────────────────────────────
    per_clause: list[ClauseAnalysis] = []
    for ca in pre_analyses:
        per_clause.append(ClauseAnalysis(
            clause=ca.clause,
            mapped_laws=mapped.get(ca.clause.clause_id),
            rule_issues=ca.rule_issues,
            llm_issues=llm_by_id.get(ca.clause.clause_id, []),
        ))

    # ── Bước 7: Finalize + persist ────────────────────────────────────────
    result = ContractAnalysisResult(
        contract=doc,
        clauses=clauses,
        missing_mandatory=missing,
        per_clause=per_clause,
        analysis_session_id=session_id,
    )
    result = finalize_report(result)

    if persist_neo4j:
        # Ghi Neo4j ở background để không block return
        try:
            await asyncio.to_thread(persist_contract_analysis, result)
        except Exception:
            logger.exception("Persist Neo4j thất bại — bỏ qua, không block kết quả.")

    return result

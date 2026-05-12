# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Orchestration pipeline."""

from __future__ import annotations

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
) -> ContractAnalysisResult:
    """
    Chạy pipeline đầy đủ.

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
        Bỏ batch LLM sau rule (tiết kiệm chi phí).
    pdf_force_ocr:
        Luôn PaddleOCR cho PDF (scan).
    pdf_detect_scan:
        Nếu True, tự phát hiện PDF ít text layer → PaddleOCR.
    persist_neo4j:
        Ghi ``ContractSession`` khi có ``NEO4J_*`` trong môi trường / `.env`.
    entities:
        Bảng ``entities`` của dataset (workspace) — seed node ``Entity`` trong Neo4j.
    relationships:
        Bảng ``relationships`` — gợi ý thêm seed qua mô tả cạnh ``RELATED_TO``.
    use_neo4j_knowledge_graph:
        Nếu True: sau ``basic_search``, mở rộng ``RELATED_TO`` trong Neo4j.
    neo4j_graph_hops:
        Độ sâu đường đi Cypher (1–3).
    """
    session_id = str(uuid.uuid4())

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
    clauses = await segment_clauses(llm, doc)
    missing = compute_missing_mandatory(clauses, raw_text=doc.raw_text)

    mapped: dict[str, MappedLawSnippet] = {}
    neo_driver = None
    try:
        if not skip_graph_mapping and text_units is not None and not text_units.empty:
            want_kg = bool(
                use_neo4j_knowledge_graph
                and entities is not None
                and not entities.empty,
            )
            if want_kg:
                neo_driver = get_driver_from_env()
                if neo_driver is None:
                    logger.info(
                        "Knowledge Graph: không có Neo4j driver — bỏ mở rộng RELATED_TO.",
                    )

            mapped = await map_all_clauses(
                config,
                text_units,
                clauses,
                entities_df=entities if want_kg else None,
                relationships_df=relationships if want_kg else None,
                neo4j_driver=neo_driver,
                neo4j_max_hops=max(1, min(int(neo4j_graph_hops), 3)),
            )
    finally:
        if neo_driver is not None:
            neo_driver.close()

    rule_ctx = RuleContext(region=wage_region.upper(), max_probation_days=max_probation_days)

    per_clause: list[ClauseAnalysis] = []
    llm_by_id: dict[str, list[ContractIssue]] = {}
    if not skip_llm_review:
        llm_by_id = await llm_clause_review_batch(
            llm,
            clauses,
            mapped,
            region=wage_region.upper(),
        )

    for c in clauses:
        ri = apply_rules(c, rule_ctx)
        li = llm_by_id.get(c.clause_id, [])
        per_clause.append(
            ClauseAnalysis(
                clause=c,
                mapped_laws=mapped.get(c.clause_id),
                rule_issues=ri,
                llm_issues=li,
            ),
        )

    result = ContractAnalysisResult(
        contract=doc,
        clauses=clauses,
        missing_mandatory=missing,
        per_clause=per_clause,
        analysis_session_id=session_id,
    )
    result = finalize_report(result)
    if persist_neo4j:
        persist_contract_analysis(result)
    return result

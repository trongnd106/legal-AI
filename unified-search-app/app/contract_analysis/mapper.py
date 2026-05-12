# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Map điều khoản: GraphRAG basic_search + Neo4j mở rộng Entity/RELATED_TO."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import pandas as pd

import graphrag.api as api
from graphrag.config.models.graph_rag_config import GraphRagConfig

from contract_analysis.entity_seed import seed_entity_ids_for_clause
from contract_analysis.neo4j_kg_expand import expand_entity_neighborhood_cypher
from contract_analysis.schema import Clause, MappedLawSnippet

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)


async def fetch_legal_context(
    config: GraphRagConfig,
    text_units: pd.DataFrame,
    clause: Clause,
    *,
    concurrency_sem: asyncio.Semaphore,
    entities_df: pd.DataFrame | None = None,
    relationships_df: pd.DataFrame | None = None,
    neo4j_driver: Driver | None = None,
    neo4j_max_hops: int = 2,
) -> MappedLawSnippet:
    """
    Bước 1: ``basic_search`` (vector trên text_units).

    Bước 2 (tuỳ chọn): seed Entity từ ``entities``/``relationships`` workspace →
    Cypher ``RELATED_TO*1..hops`` trên Neo4j.

    Kết quả gộp vào ``rag_answer`` cho downstream (detector / báo cáo).
    """
    query_parts = [
        clause.summary or clause.title or clause.original_text[:400],
        clause.category,
        "Bộ luật Lao động 2019 quy định liên quan",
    ]
    query = " ".join(p for p in query_parts if p).strip()

    async with concurrency_sem:
        try:
            response, _ctx = await api.basic_search(
                config=config,
                text_units=text_units,
                response_type="Multiple Paragraphs",
                query=query,
            )
            basic = response if isinstance(response, str) else str(response)
        except Exception as exc:
            basic = f"(Lỗi GraphRAG basic_search: {exc})"

    kg_md = ""
    note = "basic_search"
    seed_ids: list[str] = []

    if neo4j_driver is not None and entities_df is not None and not entities_df.empty:
        seed_ids = seed_entity_ids_for_clause(
            clause,
            entities_df,
            relationships_df=relationships_df,
            top_k=12,
        )
        if seed_ids:
            try:

                def _expand():
                    return expand_entity_neighborhood_cypher(
                        neo4j_driver,
                        seed_ids,
                        max_hops=neo4j_max_hops,
                    )

                kg_md = await asyncio.to_thread(_expand)
                note = "basic_search+neo4j_entity_graph"
            except Exception:
                logger.exception("Neo4j KG expand trong mapper")
                kg_md = ""

    if kg_md.strip():
        combined = (
            f"{basic[:9000]}\n\n---\n{kg_md}"
            if len(basic) + len(kg_md) < 14000
            else f"{basic[:7000]}\n\n---\n{kg_md[:6500]}"
        )
    else:
        combined = basic[:12000]

    return MappedLawSnippet(
        query_used=query,
        rag_answer=combined,
        relevance_note=note,
    )


async def map_all_clauses(
    config: GraphRagConfig,
    text_units: pd.DataFrame,
    clauses: list[Clause],
    *,
    max_concurrent: int = 2,
    entities_df: pd.DataFrame | None = None,
    relationships_df: pd.DataFrame | None = None,
    neo4j_driver: Driver | None = None,
    neo4j_max_hops: int = 2,
) -> dict[str, MappedLawSnippet]:
    """Trả dict clause_id -> snippet."""
    sem = asyncio.Semaphore(max_concurrent)

    async def one(c: Clause) -> tuple[str, MappedLawSnippet]:
        snip = await fetch_legal_context(
            config,
            text_units,
            c,
            concurrency_sem=sem,
            entities_df=entities_df,
            relationships_df=relationships_df,
            neo4j_driver=neo4j_driver,
            neo4j_max_hops=neo4j_max_hops,
        )
        return c.clause_id, snip

    pairs = await asyncio.gather(*[one(c) for c in clauses])
    return dict(pairs)

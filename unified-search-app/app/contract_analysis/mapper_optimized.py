# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Mapper tối ưu: multihop_reasoning + parquet caching."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import pandas as pd

from contract_analysis.schema import Clause, MappedLawSnippet
from query.loader import GraphLoader
from query.multihop_reasoning import VNLegalReasoningEngine, ReasoningChain

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OptimizedLegalContextMapper:
    """Mapper sử dụng multihop_reasoning + parquet caching."""

    def __init__(self, loader: GraphLoader):
        """
        Args:
            loader: GraphLoader đã load parquets
        """
        self.loader = loader
        self.engine = VNLegalReasoningEngine(loader)
        self.text_units = loader.text_units
        self.entities = loader.entities
        self.relationships = loader.relationships
        logger.info("✓ OptimizedLegalContextMapper initialized with caching")

    @lru_cache(maxsize=256)
    def _category_to_chain_type(self, category: str) -> str:
        """Map clause category → reasoning chain type."""
        mapping = {
            "SALARY": "entitlement",
            "PROBATION": "procedure",
            "TERMINATION": "violation",
            "SOCIAL_INSURANCE": "entitlement",
            "WORKING_HOURS": "entitlement",
            "PENALTY_CLAUSE": "violation",
            "UNILATERAL_TERMS": "violation",
            "WAIVER_CLAUSE": "violation",
            "NON_COMPETE": "violation",
            "DISPUTE_RESOLUTION": "procedure",
        }
        return mapping.get(category, "procedure")

    def _extract_chain_entities(self, chain: ReasoningChain) -> str:
        """Format reasoning chain thành Markdown."""
        if not chain.steps:
            return ""

        lines = [
            "### Multi-hop Reasoning Chain",
            f"**Chain Type:** {chain.chain_type}",
            "",
        ]

        for i, step in enumerate(chain.steps, 1):
            lines.append(f"**Step {i}:** {step.entity_type}")
            lines.append(f"- **Entity:** {step.entity_name} (id: `{step.entity_id}`)")
            lines.append(f"- **Relation:** {step.relation}")
            if step.description:
                lines.append(f"- **Description:** {step.description[:200]}")
            lines.append("")

        if chain.cited_articles:
            lines.append(f"**Articles:** {', '.join(chain.cited_articles)}")

        return "\n".join(lines)

    async def fetch_legal_context(
        self,
        clause: Clause,
        *,
        concurrency_sem: asyncio.Semaphore,
    ) -> MappedLawSnippet:
        """
        Lấy ngữ cảnh pháp lý tối ưu:
        1. Multihop reasoning để tìm entities liên quan
        2. Neighborhood expansion trên parquet (song song)
        3. Gộp kết quả
        """
        query_text = clause.summary or clause.title or clause.original_text[:400]
        chain_type = self._category_to_chain_type(clause.category)

        async with concurrency_sem:
            try:
                # Bước 1: Multihop reasoning (semantic search trên graph)
                chain = await asyncio.to_thread(
                    self.engine.trace_chain,
                    query_text,
                    chain_type,
                )
                chain_md = self._extract_chain_entities(chain)
                note = f"multihop_reasoning({chain_type})"
                confidence = "high"

            except Exception as exc:
                logger.debug(f"Multihop reasoning error: {exc}")
                chain_md = ""
                chain = None
                note = "multihop_reasoning_failed"
                confidence = "low"

        # Bước 2: Neighborhood expansion nếu có entities từ chain
        neighbor_md = ""
        if chain and chain.steps:
            try:
                entity_ids = [step.entity_id for step in chain.steps[:8]]
                neighbor_md = await asyncio.to_thread(
                    self._expand_entity_neighbors,
                    entity_ids,
                )
            except Exception as exc:
                logger.debug(f"Entity neighborhood expansion error: {exc}")
                neighbor_md = ""

        # Bước 3: Combine
        if neighbor_md:
            rag_answer = f"{chain_md}\n\n{neighbor_md}" if chain_md else neighbor_md
            note = f"multihop+neighbors"
        else:
            rag_answer = chain_md or "(No context found)"

        return MappedLawSnippet(
            clause_id=clause.clause_id,
            category=clause.category,
            rag_answer=rag_answer[:12000],
            note=note,
            confidence=confidence,
        )

    def _expand_entity_neighbors(
        self,
        entity_ids: list[str],
        max_hops: int = 2,
        limit: int = 25,
    ) -> str:
        """Mở rộng entity neighbors trên parquet (không dùng Neo4j)."""
        if not entity_ids or not hasattr(self.entities, 'index'):
            return ""

        # Tìm entities bằng ID
        entities_df = self.entities
        seed_entities = entities_df[entities_df['id'].isin(entity_ids)]

        if seed_entities.empty:
            return ""

        neighbors = set(entity_ids)

        # Multi-hop qua relationships
        for _ in range(max_hops):
            # Tìm relationships nơi source/target là seed entities
            rels = self.relationships[
                (self.relationships['source'].isin(neighbors))
                | (self.relationships['target'].isin(neighbors))
            ]

            if rels.empty:
                break

            # Collect neighbors
            new_neighbors = set(rels['source'].unique()) | set(rels['target'].unique())
            if new_neighbors.issubset(neighbors):
                break

            neighbors.update(new_neighbors)

        # Lấy entity info
        neighbor_entities = entities_df[
            entities_df['id'].isin(neighbors)
        ].head(limit)

        if neighbor_entities.empty:
            return ""

        lines = ["### Entity Neighborhood (Parquet)", ""]
        for _, row in neighbor_entities.iterrows():
            title = row.get('title', 'Unknown')
            ent_type = row.get('type', 'Entity')
            desc = row.get('description', '')[:150]
            lines.append(f"**{title}** ({ent_type})")
            if desc:
                lines.append(f"  {desc}")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_legal_context_optimized(
    loader: GraphLoader,
    clause: Clause,
    *,
    concurrency_sem: asyncio.Semaphore,
) -> MappedLawSnippet:
    """
    Fetch legal context sử dụng multihop reasoning + parquet.

    Usage:
        loader = GraphLoader("data/labor-law").load()
        sem = asyncio.Semaphore(4)
        context = await fetch_legal_context_optimized(loader, clause, concurrency_sem=sem)
    """
    mapper = OptimizedLegalContextMapper(loader)
    return await mapper.fetch_legal_context(clause, concurrency_sem=concurrency_sem)

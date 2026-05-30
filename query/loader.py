"""
query/loader.py — Helper dùng chung: load GraphRagConfig + parquets từ artifacts directory.

Dùng:
    from query.loader import GraphLoader
    loader = GraphLoader("data/labor-law")
    loader.load()
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig


class GraphLoader:
    """Load và giữ config + tất cả parquet DataFrames cần cho query."""

    REQUIRED_PARQUETS = [
        "create_final_entities.parquet",
        "create_final_communities.parquet",
        "create_final_community_reports.parquet",
        "create_final_text_units.parquet",
        "create_final_relationships.parquet",
    ]

    def __init__(self, root_dir: str = "data/labor-law"):
        self.root_dir = Path(root_dir)
        self.config: GraphRagConfig | None = None
        self.entities: pd.DataFrame | None = None
        self.communities: pd.DataFrame | None = None
        self.community_reports: pd.DataFrame | None = None
        self.text_units: pd.DataFrame | None = None
        self.relationships: pd.DataFrame | None = None
        self.covariates: pd.DataFrame | None = None
        self.artifacts_dir: Path | None = None

    # ------------------------------------------------------------------
    def _find_latest_artifacts(self) -> Path:
        """Tìm artifacts directory mới nhất trong output/*/artifacts/."""
        candidates = sorted(
            (self.root_dir / "output").glob("*/artifacts"),
            key=lambda p: p.parent.name,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(
                f"Không tìm thấy artifacts trong {self.root_dir}/output/. "
                "Hãy chạy 'graphrag index' trước."
            )
        return candidates[0]

    def _find_merged_graph(self) -> Path | None:
        """Trả về merged_entities.parquet directory nếu đã chạy 02_merge_structural_graph.py."""
        merged = self.root_dir / "output" / "merged_entities.parquet"
        return merged.parent if merged.exists() else None

    # ------------------------------------------------------------------
    def load(self, prefer_merged: bool = True) -> "GraphLoader":
        """Load config + tất cả parquets. Nếu prefer_merged=True, dùng merged graph nếu có."""
        self.config = load_config(self.root_dir)
        self.artifacts_dir = self._find_latest_artifacts()

        # Parquets dùng cho GraphRAG API search (phải từ artifacts)
        self.entities = pd.read_parquet(
            self.artifacts_dir / "create_final_entities.parquet"
        )
        self.communities = pd.read_parquet(
            self.artifacts_dir / "create_final_communities.parquet"
        )
        self.community_reports = pd.read_parquet(
            self.artifacts_dir / "create_final_community_reports.parquet"
        )
        self.text_units = pd.read_parquet(
            self.artifacts_dir / "create_final_text_units.parquet"
        )
        self.relationships = pd.read_parquet(
            self.artifacts_dir / "create_final_relationships.parquet"
        )

        # Covariates là optional — bỏ qua nếu không có
        cov_path = self.artifacts_dir / "create_final_covariates.parquet"
        self.covariates = pd.read_parquet(cov_path) if cov_path.exists() else None

        print(
            f"Loaded from: {self.artifacts_dir}\n"
            f"  entities:          {len(self.entities):,}\n"
            f"  communities:       {len(self.communities):,}\n"
            f"  community_reports: {len(self.community_reports):,}\n"
            f"  text_units:        {len(self.text_units):,}\n"
            f"  relationships:     {len(self.relationships):,}\n"
            f"  covariates:        {len(self.covariates) if self.covariates is not None else 'N/A'}"
        )
        return self

    def load_merged_graph(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load merged graph từ output của 02_merge_structural_graph.py.
        Trả về (merged_entities, merged_relationships) — dùng cho multi-hop reasoning.
        """
        merged_dir = self.root_dir / "output"
        ent_path = merged_dir / "merged_entities.parquet"
        rel_path = merged_dir / "merged_relationships.parquet"

        if not ent_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {ent_path}. "
                "Hãy chạy 'python scripts/02_merge_structural_graph.py' trước."
            )

        merged_entities = pd.read_parquet(ent_path)
        merged_relationships = pd.read_parquet(rel_path)
        print(
            f"Merged graph: {len(merged_entities):,} entities, "
            f"{len(merged_relationships):,} relationships"
        )
        return merged_entities, merged_relationships

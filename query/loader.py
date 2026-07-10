"""
query/loader.py — Helper dùng chung: load GraphRagConfig + parquets từ artifacts directory.

Dùng:
    from query.loader import GraphLoader
    loader = GraphLoader("data/labor-law")
    loader.load()
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.data_model.data_reader import DataReader
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider


class GraphLoader:
    """Load và giữ config + tất cả parquet DataFrames cần cho query."""

    LEGACY_PARQUETS = {
        "entities": "create_final_entities.parquet",
        "communities": "create_final_communities.parquet",
        "community_reports": "create_final_community_reports.parquet",
        "text_units": "create_final_text_units.parquet",
        "relationships": "create_final_relationships.parquet",
        "covariates": "create_final_covariates.parquet",
    }

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
    @staticmethod
    def artifacts_available(root_dir: Path) -> bool:
        """Kiểm tra index GraphRAG đã có output chưa (format mới hoặc legacy)."""
        out = root_dir / "output"
        if not out.exists():
            return False
        if (out / "entities.parquet").exists():
            return True
        return bool(list(out.glob("*/artifacts/create_final_entities.parquet")))

    def _find_latest_legacy_artifacts(self) -> Path:
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

    def _load_via_table_provider(self) -> None:
        """Load output GraphRAG mới qua TableProvider (giống graphrag CLI)."""
        storage_obj = create_storage(self.config.output_storage)
        table_provider = create_table_provider(
            self.config.table_provider, storage=storage_obj
        )
        reader = DataReader(table_provider)
        self.artifacts_dir = self.root_dir / "output"

        async def _read_all() -> None:
            self.entities = await reader.entities()
            self.communities = await reader.communities()
            self.community_reports = await reader.community_reports()
            self.text_units = await reader.text_units()
            self.relationships = await reader.relationships()
            if await table_provider.has("covariates"):
                self.covariates = await reader.covariates()
            else:
                self.covariates = None

        asyncio.run(_read_all())

    def _load_legacy_artifacts(self) -> None:
        """Load output GraphRAG legacy từ output/*/artifacts/."""
        self.artifacts_dir = self._find_latest_legacy_artifacts()
        self.entities = pd.read_parquet(
            self.artifacts_dir / self.LEGACY_PARQUETS["entities"]
        )
        self.communities = pd.read_parquet(
            self.artifacts_dir / self.LEGACY_PARQUETS["communities"]
        )
        self.community_reports = pd.read_parquet(
            self.artifacts_dir / self.LEGACY_PARQUETS["community_reports"]
        )
        self.text_units = pd.read_parquet(
            self.artifacts_dir / self.LEGACY_PARQUETS["text_units"]
        )
        self.relationships = pd.read_parquet(
            self.artifacts_dir / self.LEGACY_PARQUETS["relationships"]
        )
        cov_path = self.artifacts_dir / self.LEGACY_PARQUETS["covariates"]
        self.covariates = pd.read_parquet(cov_path) if cov_path.exists() else None

    # ------------------------------------------------------------------
    def load(self, prefer_merged: bool = True) -> "GraphLoader":
        """Load config + tất cả parquets. Nếu prefer_merged=True, dùng merged graph nếu có."""
        orig_cwd = Path.cwd()
        try:
            self.config = load_config(self.root_dir)
        finally:
            import os
            os.chdir(orig_cwd)
        if (self.root_dir / "output" / "entities.parquet").exists():
            self._load_via_table_provider()
        else:
            self._load_legacy_artifacts()

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

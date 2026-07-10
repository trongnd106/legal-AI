#!/usr/bin/env python3
"""Xoá sạch Neo4j và sync lại toàn bộ merged graph (L1 + L2).

Usage:
  python scripts/sync_neo4j_full.py [--root data/labor-law]
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

L1_REL_TYPES = {"issued_by", "guided_by", "repeals", "amends", "contains", "cites", "nested_in"}
BATCH_SIZE = 500


def _to_neo4j_val(v):
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, default=str)
    if isinstance(v, (list, tuple)):
        if not v:
            return []
        if _has_nested_map(v):
            return json.dumps(list(v), ensure_ascii=False, default=str)
        return [_to_neo4j_val(x) for x in v]
    if isinstance(v, np.ndarray):
        if v.size == 0:
            return []
        if v.dtype == object and any(isinstance(x, dict) for x in v.ravel()):
            return json.dumps(v.tolist(), ensure_ascii=False, default=str)
        flat = v.tolist()
        if isinstance(flat, list) and _has_nested_map(flat):
            return json.dumps(flat, ensure_ascii=False, default=str)
        if isinstance(flat, list):
            return [_to_neo4j_val(x) for x in flat]
        return _to_neo4j_val(flat)
    if hasattr(v, "item"):
        return v.item()
    return v


def _has_nested_map(v):
    if isinstance(v, dict):
        return True
    if isinstance(v, (list, tuple)):
        return any(_has_nested_map(x) for x in v)
    if isinstance(v, np.ndarray) and v.size and v.dtype == object:
        return any(isinstance(x, dict) for x in v.ravel())
    return False


def _df_to_rows(df, extra=None):
    rows = []
    for r in df.to_dict("records"):
        row = {k: _to_neo4j_val(v) for k, v in r.items()}
        if extra:
            row.update(extra)
        rows.append(row)
    return rows


def _batch(rows):
    for i in range(0, len(rows), BATCH_SIZE):
        yield rows[i : i + BATCH_SIZE]


def clear_all(driver):
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("  [Neo4j] Cleared all nodes & relationships")


def sync_nodes(driver, label, rows, id_field="id"):
    if not rows:
        return
    q = f"""
    UNWIND $rows AS row
    MERGE (n:{label} {{{id_field}: row.{id_field}}})
    SET n += row
    """
    with driver.session() as session:
        for batch in _batch(rows):
            session.run(q, rows=batch)
    print(f"  [Neo4j] MERGE {len(rows):>5} :{label}")


def sync_merged_entities(driver, ent_df):
    """Sync merged entities: L1 gets type label, L2 gets :Entity."""
    l1 = ent_df[ent_df["type"].isin(["VanBan", "Chuong", "Dieu", "Khoan"])]
    l2 = ent_df[~ent_df["type"].isin(["VanBan", "Chuong", "Dieu", "Khoan"])]

    # L2 entities → :Entity (giữ nguyên tương thích code cũ)
    if not l2.empty:
        l2_rows = _df_to_rows(l2)
        sync_nodes(driver, "Entity", l2_rows)

    # L1 structural nodes → mỗi type là một label riêng
    for t in ["VanBan", "Chuong", "Dieu", "Khoan"]:
        subset = l1[l1["type"] == t]
        if not subset.empty:
            rows = _df_to_rows(subset)
            sync_nodes(driver, t, rows)

    # Thêm index trên id cho tất cả label
    labels = ["Entity", "VanBan", "Chuong", "Dieu", "Khoan"]
    with driver.session() as session:
        for lbl in labels:
            try:
                session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{lbl}) ON (n.id)")
            except Exception:
                pass
    print("  [Neo4j] Indexes created")


def sync_merged_relationships(driver, rel_df):
    """Sync merged relationships.

    L1: description là keyword → MATCH source/target bằng id → tạo relationship
        với type = description.
    L2: description là text dài → MATCH :Entity bằng title → tạo :RELATED_TO.
    """
    l1 = rel_df[rel_df["description"].isin(L1_REL_TYPES)]
    l2 = rel_df[~rel_df["description"].isin(L1_REL_TYPES)]

    # Sync L1 relationships
    if not l1.empty:
        rows = _df_to_rows(l1)
        with driver.session() as session:
            for rel_type in sorted(l1["description"].unique()):
                subset = [r for r in rows if r.get("description") == rel_type]
                if not subset:
                    continue
                q = f"""
                UNWIND $rows AS row
                MATCH (src {{id: row.source}})
                MATCH (tgt {{id: row.target}})
MERGE (src)-[r:`{rel_type}` {{id: row.id}}]->(tgt)
SET r += row
                """
                for batch in _batch(subset):
                    session.run(q, rows=batch)
                print(f"    :{rel_type}: {len(subset)}")
        print(f"  [Neo4j] MERGE {len(rows):>5} L1 relationships ({l1['description'].nunique()} types)")

    # Sync L2 relationships → :RELATED_TO (giữ nguyên code cũ)
    if not l2.empty:
        rows = _df_to_rows(l2)
        q = """
        UNWIND $rows AS row
        MATCH (src:Entity {title: row.source})
        MATCH (tgt:Entity {title: row.target})
        MERGE (src)-[r:RELATED_TO {id: row.id}]->(tgt)
        SET r.human_readable_id = row.human_readable_id,
            r.description       = row.description,
            r.weight            = row.weight,
            r.combined_degree   = row.combined_degree,
            r.text_unit_ids     = row.text_unit_ids
        """
        with driver.session() as session:
            for batch in _batch(rows):
                session.run(q, rows=batch)
        print(f"  [Neo4j] MERGE {len(rows):>5} :RELATED_TO")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/labor-law")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD", ""))
    args = parser.parse_args()

    root = Path(args.root)
    output_dir = root / "output"

    if not output_dir.is_dir():
        print(f"Không tìm thấy {output_dir}")
        return 1
    if not args.neo4j_password:
        print("Cần NEO4J_PASSWORD hoặc --neo4j-password")
        return 1

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    driver.verify_connectivity()
    print(f"Connected: {args.neo4j_uri}")

    # 1. Xoá toàn bộ
    clear_all(driver)

    # 2. Sync các node GraphRAG gốc (TextUnit, Community, CommunityReport)
    # Bỏ qua Document vì merged_entities đã có :Dieu (cùng ID, trùng hoàn toàn)
    for fname, label in [
        ("text_units", "TextUnit"),
        ("community_reports", "CommunityReport"),
    ]:
        path = output_dir / f"{fname}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if not df.empty:
                rows = _df_to_rows(df, {"source_file": "labor_law"})
                sync_nodes(driver, label, rows)

    # Community nodes đặc biệt: đọc từ communities.parquet
    path = output_dir / "communities.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        if not df.empty:
            rows = _df_to_rows(df, {"source_file": "labor_law"})
            sync_nodes(driver, "Community", rows)

    # 3. Sync merged entities (L1 + L2)
    path = output_dir / "merged_entities.parquet"
    if not path.exists():
        print(f"Không tìm thấy {path} — chạy 02_merge_structural_graph.py trước")
        return 1
    ent_df = pd.read_parquet(path)
    sync_merged_entities(driver, ent_df)

    # 4. Sync merged relationships (L1 + L2)
    path = output_dir / "merged_relationships.parquet"
    if not path.exists():
        print(f"Không tìm thấy {path}")
        return 1
    rel_df = pd.read_parquet(path)
    sync_merged_relationships(driver, rel_df)

    driver.close()
    print("\nDone. All data synced to Neo4j.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

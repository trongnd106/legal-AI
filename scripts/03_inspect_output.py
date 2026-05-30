#!/usr/bin/env python3
"""
scripts/03_inspect_output.py — Skill 03 / Bước 5
=================================================
Kiểm tra output của graphrag index.

Usage:
  python3 scripts/03_inspect_output.py
  python3 scripts/03_inspect_output.py --root data/labor-law
"""

import argparse
from pathlib import Path

import pandas as pd


def find_latest_artifacts(root: Path) -> Path | None:
    candidates = sorted((root / "output").glob("*/artifacts"), reverse=True)
    return candidates[0] if candidates else None


def inspect(root: Path) -> None:
    artifacts = find_latest_artifacts(root)
    if artifacts is None:
        print("❌ Chưa có output. Chạy: .venv/bin/graphrag index --root", root)
        return

    print(f"📂 Artifacts: {artifacts.relative_to(root.parent)}\n")

    # ── Entities ──────────────────────────────────────────────────────────────
    ent_path = artifacts / "create_final_entities.parquet"
    if ent_path.exists():
        ent = pd.read_parquet(ent_path)
        print(f"Entities: {len(ent)}")
        if "type" in ent.columns:
            print(ent["type"].value_counts().to_string())
        # Cảnh báo nếu L1 structural entities lọt vào L2 output
        structural = {"VanBan", "Chuong", "Dieu", "Khoan", "Diem"}
        leaked = set(ent.get("type", pd.Series()).unique()) & structural
        if leaked:
            print(f"\n⚠️  Structural entity types lọt vào L2 output: {leaked}")
            print("   → Kiểm tra extract_graph.entity_types trong settings.yaml")
    else:
        print("⚠️  create_final_entities.parquet chưa có")

    print()

    # ── Relationships ─────────────────────────────────────────────────────────
    rel_path = artifacts / "create_final_relationships.parquet"
    if rel_path.exists():
        rels = pd.read_parquet(rel_path)
        print(f"Relationships: {len(rels)}")
        if "description" in rels.columns:
            print("\nTop relation descriptions:")
            print(rels["description"].value_counts().head(15).to_string())
    else:
        print("⚠️  create_final_relationships.parquet chưa có")

    print()

    # ── Communities ───────────────────────────────────────────────────────────
    comm_path = artifacts / "create_final_communities.parquet"
    cr_path   = artifacts / "create_final_community_reports.parquet"
    if comm_path.exists():
        comms = pd.read_parquet(comm_path)
        print(f"Communities: {len(comms)}")
        if "level" in comms.columns:
            print(comms["level"].value_counts().sort_index().to_string())
    if cr_path.exists():
        cr = pd.read_parquet(cr_path)
        print(f"\nCommunity reports: {len(cr)}")
        rank_col = "rank" if "rank" in cr.columns else None
        title_col = "title" if "title" in cr.columns else cr.columns[0]
        cols = [title_col] + ([rank_col] if rank_col else [])
        if rank_col:
            print(cr[cols].sort_values(rank_col, ascending=False).head(10).to_string(index=False))
        else:
            print(cr[cols].head(10).to_string(index=False))

    print()

    # ── Text units ────────────────────────────────────────────────────────────
    tu_path = artifacts / "create_final_text_units.parquet"
    if tu_path.exists():
        tu = pd.read_parquet(tu_path)
        print(f"Text units (chunks): {len(tu)}")
    
    print("\n✅ Kiểm tra xong. Nếu kết quả hợp lệ, chạy tiếp:")
    print("   python3 scripts/02_merge_structural_graph.py")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect graphrag index output")
    ap.add_argument("--root", default="data/labor-law")
    args = ap.parse_args()
    inspect(Path(args.root))


if __name__ == "__main__":
    main()

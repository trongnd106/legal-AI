#!/usr/bin/env python3
"""
scripts/02_merge_structural_graph.py — Skill 02 / Bước 6
=========================================================
Merge Lớp 1 (structural graph từ JSONL) vào output của GraphRAG indexing.

Pipeline:
  1. Đọc JSONL → tạo L1 entity nodes (VanBan, Chuong, Dieu, Khoan)
  2. Đọc metadata.json → tạo L1 relation (issued_by, guided_by, amends, repeals)
  3. Build alias index: (so_dieu, van_ban) → dieu_id  (context-aware, no collision)
  4. Load GraphRAG output parquets (entities + relationships)
  5. Resolve LLM relationship source/target qua alias index + chunk context
  6. Dedup CoQuan nodes: L1 metadata + L2 LLM extract có thể cùng tên → giữ 1
  7. Merge L1 + L2 → write lại parquets

Usage:
  python3 scripts/02_merge_structural_graph.py [--root data/labor-law] [--dry-run]

Output:
  data/labor-law/output/merged_entities.parquet
  data/labor-law/output/merged_relationships.parquet
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

import numpy as np
import pandas as pd


# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_ROOT = Path("data/labor-law")

# GraphRAG output dirs to search (newest run first)
# Legacy: output/<run_id>/artifacts  |  Direct: output/
GRAPHRAG_OUTPUT_GLOB = "output/*/artifacts"

# Column schemas expected by GraphRAG downstream queries
ENTITY_COLS = [
    "id", "title", "type", "description",
    "human_readable_id", "graph_embedding", "text_unit_ids",
    # domain extensions
    "norm_type", "van_ban", "chuong_so",
]
REL_COLS = [
    "id", "source", "target", "description",
    "weight", "human_readable_id", "text_unit_ids",
    "combined_degree",
]


# ─── Step 1 — Build L1 entities + rels from JSONL ────────────────────────────

def build_structural_graph(
    chunks_dir: Path,
    metadata_path: Path,
) -> tuple[list[dict], list[dict], dict[tuple[int, str], str], dict[str, str]]:
    """
    Returns:
        entities    : L1 entity rows
        rels        : L1 relationship rows
        alias_index : (so_dieu, van_ban) → dieu_id
        van_ban_slug: van_ban_id → slug string (BLLĐ_2019, ND_12_2022…)
    """
    entities: list[dict] = []
    rels: list[dict] = []
    alias_index: dict[tuple[int, str], str] = {}
    van_ban_slug: dict[str, str] = {}
    hrid = 0  # human_readable_id counter

    def next_hrid() -> int:
        nonlocal hrid
        hrid += 1
        return hrid

    # ── 1a. VanBan nodes từ metadata ─────────────────────────────────────────
    meta: dict[str, dict] = {}
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        for vid, m in meta.items():
            entities.append({
                "id": _safe_id(vid),
                "title": m.get("ten", vid),
                "type": "VanBan",
                "description": (
                    f"{m.get('loai','').replace('_',' ').title()} số {vid}. "
                    f"Ban hành: {m.get('ngay_ban_hanh','-')}, "
                    f"Hiệu lực: {m.get('ngay_hieu_luc','-')}."
                ),
                "human_readable_id": next_hrid(),
                "graph_embedding": None,
                "text_unit_ids": [],
                "norm_type": None,
                "van_ban": vid,
                "chuong_so": None,
            })
            # Track slug (e.g. "45/2019/QH14" → "BLLĐ_2019" derived from ten)
            ten = m.get("ten", "")
            slug = _ten_to_slug(ten, vid)
            van_ban_slug[vid] = slug

        # ── 1b. CoQuan L1: issued_by từ metadata ─────────────────────────────
        coquan_seen: dict[str, str] = {}  # title.lower() → id
        for vid, m in meta.items():
            co_quan_title = m.get("co_quan", "").strip()
            if not co_quan_title:
                continue
            key = co_quan_title.lower()
            if key not in coquan_seen:
                cq_id = "CQ_" + re.sub(r"\W+", "_", co_quan_title).strip("_")
                coquan_seen[key] = cq_id
                entities.append({
                    "id": cq_id,
                    "title": co_quan_title,
                    "type": "CoQuan",
                    "description": f"Cơ quan ban hành văn bản pháp luật lao động",
                    "human_readable_id": next_hrid(),
                    "graph_embedding": None,
                    "text_unit_ids": [],
                    "norm_type": None,
                    "van_ban": None,
                    "chuong_so": None,
                })
            # issued_by relation
            rels.append({
                "id": str(uuid.uuid4()),
                "source": _safe_id(vid),
                "target": coquan_seen[key],
                "description": "issued_by",
                "weight": 10.0,
                "human_readable_id": next_hrid(),
                "text_unit_ids": [],
                "combined_degree": 0,
            })

        # ── 1c. VanBan→VanBan relations từ metadata ──────────────────────────
        for vid, m in meta.items():
            src = _safe_id(vid)
            for field, rel_type in [
                ("huong_dan_cho", "guided_by"),
                ("thay_the",      "repeals"),
                ("sua_doi",       "amends"),
            ]:
                targets = m.get(field)
                if not targets:
                    continue
                if isinstance(targets, str):
                    targets = [targets]
                for t in targets:
                    rels.append({
                        "id": str(uuid.uuid4()),
                        "source": src,
                        "target": _safe_id(t),
                        "description": rel_type,
                        "weight": 8.0,
                        "human_readable_id": next_hrid(),
                        "text_unit_ids": [],
                        "combined_degree": 0,
                    })
            # huong_dan_boi (list of NĐ hướng dẫn)
            for t in m.get("huong_dan_boi", []):
                rels.append({
                    "id": str(uuid.uuid4()),
                    "source": src,
                    "target": _safe_id(t),
                    "description": "guided_by",
                    "weight": 7.0,
                    "human_readable_id": next_hrid(),
                    "text_unit_ids": [],
                    "combined_degree": 0,
                })

    # ── 1d. Dieu + Khoan nodes từ JSONL ──────────────────────────────────────
    chuong_seen: set[str] = set()

    for jsonl in sorted(chunks_dir.glob("*.jsonl")):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            dieu_id = r["id"]
            so = r["so_dieu"]
            van_ban = r["van_ban"]

            # Alias index: context-aware tuple key → tránh collision
            alias_index[(so, van_ban)] = dieu_id
            # slug map từ file stem (e.g. "BLLĐ_2019")
            if van_ban not in van_ban_slug:
                van_ban_slug[van_ban] = jsonl.stem

            # Chuong node (dedup)
            chuong_id = f"{_safe_id(van_ban)}_Chương_{r.get('chuong_so','?')}"
            if chuong_id not in chuong_seen:
                chuong_seen.add(chuong_id)
                entities.append({
                    "id": chuong_id,
                    "title": f"Chương {r.get('chuong_so','')} — {r.get('ten_chuong','')}",
                    "type": "Chuong",
                    "description": r.get("ten_chuong", ""),
                    "human_readable_id": next_hrid(),
                    "graph_embedding": None,
                    "text_unit_ids": [],
                    "norm_type": None,
                    "van_ban": van_ban,
                    "chuong_so": r.get("chuong_so"),
                })
                # VanBan --contains--> Chuong
                rels.append({
                    "id": str(uuid.uuid4()),
                    "source": _safe_id(van_ban),
                    "target": chuong_id,
                    "description": "contains",
                    "weight": 10.0,
                    "human_readable_id": next_hrid(),
                    "text_unit_ids": [],
                    "combined_degree": 0,
                })

            # Dieu node
            noi_dung = r.get("noi_dung", "")
            entities.append({
                "id": dieu_id,
                "title": f"Điều {so}. {r.get('tieu_de', '')}",
                "type": "Dieu",
                "description": noi_dung[:600] + ("…" if len(noi_dung) > 600 else ""),
                "human_readable_id": next_hrid(),
                "graph_embedding": None,
                "text_unit_ids": [dieu_id],
                "norm_type": r.get("norm_type"),
                "van_ban": van_ban,
                "chuong_so": r.get("chuong_so"),
            })
            # Chuong --contains--> Dieu
            rels.append({
                "id": str(uuid.uuid4()),
                "source": chuong_id,
                "target": dieu_id,
                "description": "contains",
                "weight": 10.0,
                "human_readable_id": next_hrid(),
                "text_unit_ids": [],
                "combined_degree": 0,
            })

            # Khoan nodes
            for k in r.get("khoans", []):
                kid = f"{dieu_id}_Khoản_{k['so']}"
                knoi_dung = k.get("noi_dung", "")
                entities.append({
                    "id": kid,
                    "title": f"Khoản {k['so']} Điều {so}",
                    "type": "Khoan",
                    "description": knoi_dung[:300] + ("…" if len(knoi_dung) > 300 else ""),
                    "human_readable_id": next_hrid(),
                    "graph_embedding": None,
                    "text_unit_ids": [dieu_id],
                    "norm_type": None,
                    "van_ban": van_ban,
                    "chuong_so": None,
                })
                rels.append({
                    "id": str(uuid.uuid4()),
                    "source": dieu_id,
                    "target": kid,
                    "description": "contains",
                    "weight": 10.0,
                    "human_readable_id": next_hrid(),
                    "text_unit_ids": [],
                    "combined_degree": 0,
                })

    return entities, rels, alias_index, van_ban_slug


# ─── Step 3 — Alias resolution ───────────────────────────────────────────────

def resolve_alias(
    name: str,
    chunk_van_ban: str,
    alias_index: dict[tuple[int, str], str],
    van_ban_slug: dict[str, str],
) -> str:
    """
    Map LLM-generated name → L1 dieu_id.

    Priority:
      1. "Điều 35 45/2019/QH14" hoặc "Điều 35 BLLĐ 2019" → lookup chính xác
      2. "Điều 35" không có văn bản → fallback sang chunk_van_ban
      3. Không resolve được → giữ nguyên string
    """
    name = name.strip()
    m = re.match(r"[Đđ]iều\s+(\d+)", name, re.IGNORECASE)
    if not m:
        return name

    so = int(m.group(1))
    rest = name[m.end():].strip()

    # Thử match văn bản cụ thể trong phần còn lại
    for (s, vb), dieu_id in alias_index.items():
        if s != so:
            continue
        slug = van_ban_slug.get(vb, "")
        if vb in rest or (slug and slug in rest):
            return dieu_id

    # Fallback: dùng van_ban của chunk đang xử lý
    key = (so, chunk_van_ban)
    return alias_index.get(key, name)


# ─── Step 4+5 — Load GraphRAG output + resolve aliases ───────────────────────

def load_graphrag_output(root: Path) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Tìm GraphRAG output parquet files.

    Thử theo thứ tự:
      1. output/<run_id>/artifacts/create_final_entities.parquet (legacy)
      2. output/entities.parquet (từ phiên bản GraphRAG cũ hơn hoặc index chạy trực tiếp)
    """
    # Legacy: output/*/artifacts/
    artifacts_dirs = sorted(root.glob("output/*/artifacts"), reverse=True)
    if artifacts_dirs:
        art = artifacts_dirs[0]
        ent_path = art / "create_final_entities.parquet"
        rel_path = art / "create_final_relationships.parquet"
        ent_df = pd.read_parquet(ent_path) if ent_path.exists() else None
        rel_df = pd.read_parquet(rel_path) if rel_path.exists() else None
        if ent_df is not None:
            return ent_df, rel_df

    # Fallback: output/*.parquet trực tiếp
    output_dir = root / "output"
    ent_path = output_dir / "entities.parquet"
    rel_path = output_dir / "relationships.parquet"

    ent_df = pd.read_parquet(ent_path) if ent_path.exists() else None
    rel_df = pd.read_parquet(rel_path) if rel_path.exists() else None
    return ent_df, rel_df


def resolve_llm_relationships(
    rel_df: pd.DataFrame,
    alias_index: dict[tuple[int, str], str],
    van_ban_slug: dict[str, str],
) -> pd.DataFrame:
    """Rewrite source/target trong LLM relationships qua alias index."""
    if rel_df is None or rel_df.empty:
        return rel_df

    df = rel_df.copy()
    # Lấy van_ban từ text_unit_ids nếu có (format: BLLĐ_2019_Điều_35)
    def _get_van_ban(row: pd.Series) -> str:
        raw = row.get("text_unit_ids")
        if isinstance(raw, np.ndarray):
            tids = raw.tolist()
        elif isinstance(raw, list):
            tids = raw
        elif pd.isna(raw):
            tids = []
        else:
            tids = [raw]
        for tid in tids:
            # Thử extract van_ban từ chunk text_unit_id
            for vb in van_ban_slug:
                slug = van_ban_slug[vb]
                if slug and tid.startswith(slug):
                    return vb
        return ""

    for idx, row in df.iterrows():
        chunk_vb = _get_van_ban(row)
        df.at[idx, "source"] = resolve_alias(
            str(row["source"]), chunk_vb, alias_index, van_ban_slug
        )
        df.at[idx, "target"] = resolve_alias(
            str(row["target"]), chunk_vb, alias_index, van_ban_slug
        )
    return df


# ─── Step 6 — Dedup CoQuan ────────────────────────────────────────────────────

def dedup_coquan(entities: list[dict]) -> list[dict]:
    """
    Merge CoQuan nodes có cùng title từ L1 (metadata) và L2 (LLM extraction).
    L1 node được giữ lại (đã có id có cấu trúc CQ_*).
    L2 node trùng tên bị loại bỏ.
    """
    seen: dict[str, str] = {}   # title.lower() → id được giữ lại
    id_remap: dict[str, str] = {}  # id L2 bị loại → id L1 thay thế
    result = []

    for e in entities:
        if e["type"] != "CoQuan":
            result.append(e)
            continue
        key = e["title"].lower().strip()
        if key not in seen:
            seen[key] = e["id"]
            result.append(e)
        else:
            id_remap[e["id"]] = seen[key]

    return result, id_remap


def apply_remap(
    rel_rows: list[dict],
    rel_df: pd.DataFrame | None,
    id_remap: dict[str, str],
) -> tuple[list[dict], pd.DataFrame | None]:
    """Áp dụng id_remap từ dedup_coquan vào relationships."""
    for r in rel_rows:
        r["source"] = id_remap.get(r["source"], r["source"])
        r["target"] = id_remap.get(r["target"], r["target"])

    if rel_df is not None and not rel_df.empty and id_remap:
        df = rel_df.copy()
        df["source"] = df["source"].map(lambda x: id_remap.get(x, x))
        df["target"] = df["target"].map(lambda x: id_remap.get(x, x))
        return rel_rows, df

    return rel_rows, rel_df


# ─── Step 7 — Merge + write parquets ─────────────────────────────────────────

def _align_columns(
    df: pd.DataFrame,
    cols: list[str],
    fill: object = None,
) -> pd.DataFrame:
    """Thêm cột thiếu vào DataFrame để align với schema kỳ vọng."""
    missing = [c for c in cols if c not in df.columns]
    for c in missing:
        df[c] = fill
    return df


def merge_and_save(
    l1_entities: list[dict],
    l1_rels: list[dict],
    l2_ent_df: pd.DataFrame | None,
    l2_rel_df: pd.DataFrame | None,
    output_dir: Path,
    dry_run: bool = False,
) -> None:
    l1_ent_df = pd.DataFrame(l1_entities)
    l1_rel_df = pd.DataFrame(l1_rels)

    # ── Ensure column compatibility ──────────────────────────────────────────
    # L1 columns: id, title, type, description, human_readable_id,
    #             graph_embedding, text_unit_ids, norm_type, van_ban, chuong_so
    # L2 columns: id, human_readable_id, title, type, description,
    #             text_unit_ids, frequency, degree
    # → fill missing columns với None để concat an toàn

    if l2_ent_df is not None:
        l2_ent_df = _align_columns(l2_ent_df, list(l1_ent_df.columns))
        l1_ent_df = _align_columns(l1_ent_df, list(l2_ent_df.columns))

    if l2_rel_df is not None:
        l2_rel_df = _align_columns(l2_rel_df, list(l1_rel_df.columns))
        l1_rel_df = _align_columns(l1_rel_df, list(l2_rel_df.columns))

    # Ghép L1 + L2
    ent_frames = [l1_ent_df]
    rel_frames = [l1_rel_df]

    if l2_ent_df is not None and not l2_ent_df.empty:
        # Chỉ giữ L2 entities KHÔNG phải lớp 1 structural
        structural_types = {"VanBan", "Chuong", "Dieu", "Khoan", "Diem"}
        if "type" in l2_ent_df.columns:
            l2_ent_df = l2_ent_df[~l2_ent_df["type"].isin(structural_types)]
        ent_frames.append(l2_ent_df)

    if l2_rel_df is not None and not l2_rel_df.empty:
        rel_frames.append(l2_rel_df)

    merged_ent = pd.concat(ent_frames, ignore_index=True)
    merged_rel = pd.concat(rel_frames, ignore_index=True)

    # Drop duplicate entity ids (L1 ưu tiên)
    merged_ent = merged_ent.drop_duplicates(subset=["id"], keep="first")

    # Cập nhật combined_degree
    src_counts = merged_rel["source"].value_counts()
    tgt_counts = merged_rel["target"].value_counts()
    merged_rel["combined_degree"] = (
        merged_rel["source"].map(src_counts).fillna(0)
        + merged_rel["target"].map(tgt_counts).fillna(0)
    ).astype(int)

    output_dir.mkdir(parents=True, exist_ok=True)
    ent_out = output_dir / "merged_entities.parquet"
    rel_out = output_dir / "merged_relationships.parquet"

    if dry_run:
        print(f"[DRY RUN] Would write:")
        print(f"  {ent_out}: {len(merged_ent)} entities")
        print(f"  {rel_out}: {len(merged_rel)} relationships")
        _print_stats(merged_ent, merged_rel)
        return

    merged_ent.to_parquet(ent_out, index=False)
    merged_rel.to_parquet(rel_out, index=False)
    print(f"✅ Đã ghi:")
    print(f"  {ent_out}: {len(merged_ent)} entities")
    print(f"  {rel_out}: {len(merged_rel)} relationships")
    _print_stats(merged_ent, merged_rel)


def _print_stats(ent_df: pd.DataFrame, rel_df: pd.DataFrame) -> None:
    print("\n--- Entity types ---")
    if "type" in ent_df.columns:
        print(ent_df["type"].value_counts().to_string())
    print("\n--- Relation types (description) ---")
    if "description" in rel_df.columns:
        print(rel_df["description"].value_counts().head(20).to_string())
    print()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe_id(s: str) -> str:
    """Tạo id an toàn từ string (bỏ ký tự đặc biệt)."""
    return re.sub(r"[^\w]", "_", s).strip("_")


def _ten_to_slug(ten: str, fallback: str) -> str:
    """VD: 'Bộ luật Lao động 2019' → 'BLLĐ_2019'."""
    m = re.search(r"\d{4}", ten)
    year = m.group() if m else ""
    if "Bộ luật Lao động" in ten or "BLLĐ" in ten:
        return f"BLLĐ_{year}"
    if "Nghị định" in ten:
        so = re.search(r"(\d+/\d{4}/NĐ-CP)", fallback)
        slug = so.group(1).replace("/", "_") if so else fallback
        return re.sub(r"[^\w]", "_", slug).strip("_")
    if "Thông tư" in ten:
        return re.sub(r"[^\w]", "_", fallback).strip("_")
    return re.sub(r"[^\w]", "_", fallback).strip("_")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge L1 structural graph vào GraphRAG output",
    )
    parser.add_argument("--root", default="data/labor-law", help="GraphRAG root dir")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Chỉ in thống kê, không ghi file",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Kiểm tra alias index, không merge",
    )
    args = parser.parse_args()

    root = Path(args.root)
    chunks_dir = root / "chunks"
    metadata_path = root / "metadata.json"
    output_dir = root / "output"

    print(f"📂 Root: {root.resolve()}")

    # Step 1-2: Build L1
    print("⏳ Building L1 structural graph…")
    l1_entities, l1_rels, alias_index, van_ban_slug = build_structural_graph(
        chunks_dir, metadata_path
    )
    print(f"   L1 entities: {len(l1_entities)}")
    print(f"   L1 relations: {len(l1_rels)}")
    print(f"   Alias index: {len(alias_index)} (Dieu, van_ban) tuples")

    if args.verify:
        print("\n--- Alias index sample (first 10) ---")
        for (so, vb), did in list(alias_index.items())[:10]:
            print(f"  (Điều {so:3d}, {vb:25s}) → {did}")
        print("\n--- VanBan slugs ---")
        for vb, slug in van_ban_slug.items():
            print(f"  {vb:25s} → {slug}")
        return

    # Step 4: Load GraphRAG L2 output
    print("⏳ Loading GraphRAG output…")
    l2_ent_df, l2_rel_df = load_graphrag_output(root)
    if l2_ent_df is None:
        print("⚠️  Chưa có GraphRAG output — chỉ ghi L1 structural graph.")
    else:
        print(f"   L2 entities: {len(l2_ent_df)}")
        print(f"   L2 relations: {len(l2_rel_df) if l2_rel_df is not None else 0}")

    # Step 5: Resolve aliases in L2 relationships
    if l2_rel_df is not None:
        print("⏳ Resolving aliases in LLM relationships…")
        l2_rel_df = resolve_llm_relationships(l2_rel_df, alias_index, van_ban_slug)

    # Step 6: Dedup CoQuan
    print("⏳ Deduplicating CoQuan nodes…")
    l1_entities, id_remap = dedup_coquan(l1_entities)
    if id_remap:
        print(f"   Merged {len(id_remap)} duplicate CoQuan node(s)")
        l1_rels, l2_rel_df = apply_remap(l1_rels, l2_rel_df, id_remap)

    # Step 7: Merge + save
    print("⏳ Merging and saving…")
    merge_and_save(l1_entities, l1_rels, l2_ent_df, l2_rel_df, output_dir, args.dry_run)


if __name__ == "__main__":
    main()

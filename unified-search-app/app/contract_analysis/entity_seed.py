# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Chọn entity GraphRAG (workspace) làm seed cho truy vấn Neo4j RELATED_TO."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from contract_analysis.schema import Clause


_CATEGORY_TERMS: dict[str, list[str]] = {
    "SALARY": ["lương", "tiền lương", "trả lương", "phụ cấp", "thù lao"],
    "WORKING_HOURS": ["giờ làm", "ca làm", "thời giờ", "làm thêm", "nghỉ"],
    "PROBATION": ["thử việc", "học việc"],
    "SOCIAL_INSURANCE": ["bhxh", "bảo hiểm xã hội", "bảo hiểm", "bhyt"],
    "CONTRACT_DURATION": ["thời hạn", "hợp đồng", "xác định"],
    "TERMINATION": ["chấm dứt", "thôi việc", "sa thải", "nghỉ việc"],
    "LEAVE": ["phép", "nghỉ phép", "nghỉ lễ"],
    "JOB_DESCRIPTION": ["công việc", "chức danh", "nhiệm vụ"],
    "WORKPLACE": ["địa điểm", "làm việc"],
}


def _tokenize(text: str) -> set[str]:
    text = (text or "").lower()
    parts = re.findall(
        r"[a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+",
        text,
        flags=re.IGNORECASE,
    )
    return {p for p in parts if len(p) > 2}


def _clause_blob(clause: Clause) -> str:
    return f"{clause.title}\n{clause.summary}\n{clause.original_text}".lower()


def seed_entity_ids_for_clause(
    clause: Clause,
    entities_df: pd.DataFrame,
    *,
    relationships_df: pd.DataFrame | None = None,
    top_k: int = 12,
) -> list[str]:
    """
    Xếp hạng ``Entity.id`` theo overlap token với điều khoản + gợi ý theo category.

    Tuỳ chọn: thêm entity là đầu/cuối ``RELATED_TO`` nếu mô tả cạnh khớp token.
    """
    if entities_df is None or entities_df.empty or "id" not in entities_df.columns:
        return []

    id_col, title_col, desc_col = "id", "title", "description"
    blob = _clause_blob(clause)
    tokens = _tokenize(blob)
    cat = (clause.category or "").upper()
    for term in _CATEGORY_TERMS.get(cat, []):
        tokens.update(_tokenize(term))

    scores: dict[str, float] = {}

    for _, row in entities_df.iterrows():
        eid = str(row.get(id_col) or "")
        if not eid:
            continue
        title = str(row.get(title_col) or "").lower()
        desc = str(row.get(desc_col) or "").lower()
        hay = f"{title} {desc}"
        sc = 0.0
        for tok in tokens:
            if tok in title:
                sc += 3.0
            elif tok in desc:
                sc += 1.0
        if sc > 0:
            scores[eid] = sc

    # Boost theo degree nếu có
    if "degree" in entities_df.columns:
        deg_map = dict(zip(entities_df[id_col].astype(str), entities_df["degree"], strict=False))
        for eid in list(scores.keys()):
            try:
                d = float(deg_map.get(eid) or 0)
                scores[eid] += min(d * 0.15, 5.0)
            except (TypeError, ValueError):
                pass

    # Quan hệ: mô tả cạnh khớp token → lấy entity hai đầu
    if relationships_df is not None and not relationships_df.empty:
        src_col, tgt_col = "source", "target"
        if src_col in relationships_df.columns and tgt_col in relationships_df.columns:
            title_to_id = {}
            if title_col in entities_df.columns:
                title_to_id = dict(
                    zip(
                        entities_df[title_col].astype(str),
                        entities_df[id_col].astype(str),
                        strict=False,
                    ),
                )
            desc_rel = "description"
            for _, row in relationships_df.iterrows():
                rd = str(row.get(desc_rel, "") or "").lower()
                if not any(t in rd for t in tokens if len(t) > 3):
                    continue
                for key in (row.get(src_col), row.get(tgt_col)):
                    if key is None:
                        continue
                    sid = title_to_id.get(str(key))
                    if sid:
                        scores[str(sid)] = scores.get(str(sid), 0.0) + 2.0

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [eid for eid, _ in ranked[:top_k]]

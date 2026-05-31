"""Cấu hình API — đường dẫn và hằng số."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LABOR_LAW_ROOT = REPO_ROOT / "data" / "labor-law"
METADATA_PATH = LABOR_LAW_ROOT / "metadata.json"
NORMALIZED_DIR = LABOR_LAW_ROOT / "normalized"
UPLOADS_DIR = LABOR_LAW_ROOT / "uploads"
FRONTEND_DIR = REPO_ROOT / "frontend"

# so_hieu → slug (từ scripts/01_prepare_data.py FILE_MAP)
SO_HIEU_TO_SLUG: dict[str, str] = {
    "45/2019/QH14": "BLLĐ_2019",
    "145/2020/NĐ-CP": "ND_145_2020",
    "12/2022/NĐ-CP": "ND_12_2022",
    "74/2024/NĐ-CP": "ND_74_2024",
    "70/2023/NĐ-CP": "ND_70_2023",
    "10/2020/TT-BLĐTBXH": "TT_10_2020",
    "19/VBHN-VPQH": "VBHN_BHXH",
}

SLUG_TO_SO_HIEU = {v: k for k, v in SO_HIEU_TO_SLUG.items()}

PREVIEW_MAX_CHARS = 12_000

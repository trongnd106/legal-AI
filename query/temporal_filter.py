"""
query/temporal_filter.py — Lọc kết quả theo hiệu lực văn bản pháp luật.

Tích hợp vào pipeline sau bước retrieval, trước khi trả kết quả cho người dùng.

Schema metadata.json thực tế (data/labor-law/metadata.json):
    {
        "45/2019/QH14": {
            "ten":          "Bộ luật Lao động 2019",
            "so_hieu":      "45/2019/QH14",
            "loai":         "bo_luat",
            "ngay_ban_hanh":"2019-11-20",
            "ngay_hieu_luc":"2021-01-01",
            "tinh_trang":   "con_hieu_luc",   # hoặc "het_hieu_luc"
            "co_quan":      "Quoc hoi",
            ...
        },
        ...
    }
"""
from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_META_PATH = "data/labor-law/metadata.json"


@lru_cache(maxsize=1)
def load_effectiveness_index(
    meta_path: str = DEFAULT_META_PATH,
) -> dict[str, dict[str, Any]]:
    """
    Load và cache index hiệu lực từ metadata.json.

    Returns
    -------
    dict[so_hieu, {tinh_trang, ngay_hieu_luc, ten}]
    """
    path = Path(meta_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy metadata tại {path}. "
            "Hãy chạy 'python scripts/01_prepare_data.py' trước."
        )

    with open(path, encoding="utf-8") as f:
        raw: dict = json.load(f)

    index: dict[str, dict[str, Any]] = {}
    for so_hieu, info in raw.items():
        index[so_hieu] = {
            "tinh_trang":    info.get("tinh_trang", "con_hieu_luc"),
            "ngay_hieu_luc": info.get("ngay_hieu_luc", ""),
            "ten":           info.get("ten", so_hieu),
        }
    return index


def is_effective(van_ban_id: str, as_of: date | None = None) -> bool:
    """
    Kiểm tra văn bản có còn hiệu lực tại thời điểm as_of không.

    Parameters
    ----------
    van_ban_id:
        Số hiệu văn bản đúng như key trong metadata.json
        (ví dụ: "45/2019/QH14", "12/2022/NĐ-CP").
    as_of:
        Thời điểm kiểm tra. Mặc định: hôm nay.
    """
    as_of = as_of or date.today()
    try:
        idx = load_effectiveness_index()
    except FileNotFoundError:
        return True   # Không có metadata → giả định còn hiệu lực

    info = idx.get(van_ban_id)
    if not info:
        return True   # Không có thông tin → giả định còn hiệu lực

    if info["tinh_trang"] == "het_hieu_luc":
        return False

    if info["ngay_hieu_luc"]:
        try:
            hieu_luc_date = date.fromisoformat(info["ngay_hieu_luc"])
            if as_of < hieu_luc_date:
                return False   # chưa có hiệu lực
        except ValueError:
            pass

    return True


def filter_citations_by_effectiveness(
    citations: list[str],
    as_of: date | None = None,
) -> dict[str, list[str]]:
    """
    Kiểm tra danh sách trích dẫn và đánh dấu những trích dẫn từ văn bản hết hiệu lực.

    Parameters
    ----------
    citations:
        Danh sách chuỗi trích dẫn (ví dụ: ["Điều 35 BLLĐ 2019", "Điều 4 NĐ 12/2022"]).
    as_of:
        Thời điểm kiểm tra hiệu lực. Mặc định: hôm nay.

    Returns
    -------
    dict với:
        valid_citations   : list[str] — citation từ văn bản còn hiệu lực
        expired_warnings  : list[str] — cảnh báo văn bản hết/chưa có hiệu lực
    """
    as_of = as_of or date.today()
    valid:    list[str] = []
    warnings: list[str] = []

    # Các pattern nhận dạng số hiệu văn bản trong chuỗi citation
    VB_PATTERNS = [
        r"\b(\d+/\d{4}/(?:QH|NĐ|TT|NQ|CT)\w*)",   # 45/2019/QH14, 12/2022/NĐ-CP
        r"\b(NĐ[\s-]?\d+/\d{4})",                   # NĐ 12/2022
        r"\b(TT[\s-]?\d+/\d{4})",                   # TT 10/2020
    ]

    for cite in citations:
        found_id: str | None = None
        for pattern in VB_PATTERNS:
            m = re.search(pattern, cite, re.IGNORECASE)
            if m:
                found_id = m.group(1).strip().replace(" ", "")
                break

        if found_id and not is_effective(found_id, as_of):
            try:
                idx   = load_effectiveness_index()
                ten   = idx.get(found_id, {}).get("ten", found_id)
            except FileNotFoundError:
                ten = found_id
            warnings.append(
                f"⚠️ Trích dẫn '{cite}' có thể thuộc văn bản hết hiệu lực "
                f"({ten}). Kiểm tra tại vbpl.vn."
            )
        else:
            valid.append(cite)

    return {"valid_citations": valid, "expired_warnings": warnings}


# ---------------------------------------------------------------------------
# Ví dụ CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Kiểm tra nhanh
    test_ids = ["45/2019/QH14", "12/2022/NĐ-CP", "74/2024/NĐ-CP", "FAKE/2000/QH"]
    for vid in test_ids:
        status = "còn hiệu lực" if is_effective(vid) else "hết/chưa có hiệu lực"
        print(f"{vid:30s} → {status}")

    print()
    cites = ["Điều 35 BLLĐ 45/2019/QH14", "Điều 4 NĐ 12/2022"]
    result = filter_citations_by_effectiveness(cites)
    print("Valid:", result["valid_citations"])
    print("Warnings:", result["expired_warnings"])

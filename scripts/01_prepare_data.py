#!/usr/bin/env python3
"""
Script: scripts/01_prepare_data.py
Checklist: 1.3 · 1.4 · 1.5  (bỏ qua 1.1/1.2 — file .txt đã có sẵn)

Đầu vào : data/txt/*.txt
Đầu ra  :
  data/labor-law/normalized/   ← .txt đã làm sạch   (1.4)
  data/labor-law/chunks/       ← .jsonl per-Điều     (1.3 + 1.4)
  data/labor-law/metadata.json ← hiệu lực văn bản    (1.5)

Chạy:
  python scripts/01_prepare_data.py
  python scripts/01_prepare_data.py --verify
  python scripts/01_prepare_data.py --only BLLĐ-45-2019.txt --verify
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ─── Đường dẫn ───────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "data" / "txt"
OUT_BASE  = REPO_ROOT / "data" / "labor-law"
NORM_DIR  = OUT_BASE / "normalized"
CHUNK_DIR = OUT_BASE / "chunks"
META_FILE = OUT_BASE / "metadata.json"

# ─── Mapping file → (van_ban_id, slug dùng làm prefix của id) ────────────────

FILE_MAP: dict[str, tuple[str, str]] = {
    "BLLĐ-45-2019.txt":         ("45/2019/QH14",        "BLLĐ_2019"),
    "NĐ_145-2020_NĐ-CP .txt":   ("145/2020/NĐ-CP",      "ND_145_2020"),
    "NĐ_12-2022_NĐ-CP.txt":     ("12/2022/NĐ-CP",       "ND_12_2022"),
    "NĐ_74-2024_ND-CP.txt":     ("74/2024/NĐ-CP",       "ND_74_2024"),
    "NĐ_70-2023_ND-CP.txt":     ("70/2023/NĐ-CP",       "ND_70_2023"),
    "10-2020_TT-BLDTBXH.txt":   ("10/2020/TT-BLĐTBXH",  "TT_10_2020"),
    "VBHN-BHXH.txt":            ("19/VBHN-VPQH",         "VBHN_BHXH"),
}

# ─── Metadata 1.5 ─────────────────────────────────────────────────────────────

METADATA: dict[str, dict] = {
    "45/2019/QH14": {
        "ten": "Bộ luật Lao động 2019",
        "so_hieu": "45/2019/QH14",
        "loai": "bo_luat",
        "ngay_ban_hanh": "2019-11-20",
        "ngay_hieu_luc": "2021-01-01",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Quoc hoi",
        "huong_dan_boi": ["145/2020/NĐ-CP", "12/2022/NĐ-CP", "74/2024/NĐ-CP",
                          "70/2023/NĐ-CP", "10/2020/TT-BLĐTBXH"],
    },
    "145/2020/NĐ-CP": {
        "ten": "Nghị định 145/2020/NĐ-CP — Điều kiện lao động và quan hệ lao động",
        "so_hieu": "145/2020/NĐ-CP",
        "loai": "nghi_dinh",
        "ngay_ban_hanh": "2020-12-14",
        "ngay_hieu_luc": "2021-02-01",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Chinh phu",
        "huong_dan_cho": "45/2019/QH14",
    },
    "12/2022/NĐ-CP": {
        "ten": "Nghị định 12/2022/NĐ-CP — Xử phạt vi phạm hành chính lĩnh vực lao động",
        "so_hieu": "12/2022/NĐ-CP",
        "loai": "nghi_dinh",
        "ngay_ban_hanh": "2022-01-17",
        "ngay_hieu_luc": "2022-01-17",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Chinh phu",
        "lien_quan_den": "45/2019/QH14",
    },
    "74/2024/NĐ-CP": {
        "ten": "Nghị định 74/2024/NĐ-CP — Mức lương tối thiểu",
        "so_hieu": "74/2024/NĐ-CP",
        "loai": "nghi_dinh",
        "ngay_ban_hanh": "2024-06-30",
        "ngay_hieu_luc": "2024-07-01",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Chinh phu",
        "huong_dan_cho": "45/2019/QH14",
        "thay_the": "38/2022/NĐ-CP",
    },
    "70/2023/NĐ-CP": {
        "ten": "Nghị định 70/2023/NĐ-CP — Lao động nước ngoài tại Việt Nam",
        "so_hieu": "70/2023/NĐ-CP",
        "loai": "nghi_dinh",
        "ngay_ban_hanh": "2023-09-18",
        "ngay_hieu_luc": "2023-09-18",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Chinh phu",
        "sua_doi": "152/2020/NĐ-CP",
        "lien_quan_den": "45/2019/QH14",
    },
    "10/2020/TT-BLĐTBXH": {
        "ten": "Thông tư 10/2020/TT-BLĐTBXH — Nội dung hợp đồng lao động",
        "so_hieu": "10/2020/TT-BLĐTBXH",
        "loai": "thong_tu",
        "ngay_ban_hanh": "2020-11-12",
        "ngay_hieu_luc": "2021-01-01",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Bo LDTBXH",
        "huong_dan_cho": "45/2019/QH14",
    },
    "19/VBHN-VPQH": {
        "ten": "Luật Bảo hiểm xã hội 2024 (văn bản hợp nhất)",
        "so_hieu": "19/VBHN-VPQH",
        "loai": "luat",
        "ngay_ban_hanh": "2026-02-12",
        "ngay_hieu_luc": "2025-07-01",
        "tinh_trang": "con_hieu_luc",
        "pham_vi": "toan_quoc",
        "co_quan": "Van phong Quoc hoi",
        "goc": "41/2024/QH15",
        "ghi_chu": "Hợp nhất: Luật 41/2024/QH15 + Luật Nhà giáo 73/2025 + Luật Thanh tra 84/2025",
    },
}

# ─── Regex patterns ────────────────────────────────────────────────────────────

RE_PHAN   = re.compile(r"^Phần\s+(thứ\s+)?\w+", re.IGNORECASE)
RE_CHUONG = re.compile(r"^Chương\s+([IVXLCDM\d]+)\s*$")
RE_MUC    = re.compile(r"^Mục\s+(\d+)\s*$")
RE_DIEU   = re.compile(r"^Điều\s+(\d+)[\.:]?\s*(.*)")
# Khoản: số theo sau dấu chấm ở đầu dòng, nhưng không phải Điều
RE_KHOAN  = re.compile(r"^(\d+)\.\s+(.+)", re.DOTALL)
# Điểm: ký hiệu chữ thường a-z và đ
RE_DIEM   = re.compile(r"^([a-zđ])\)\s+(.+)", re.DOTALL)
# Separator thuần (dấu gạch, gạch dưới, bằng)
RE_SEP    = re.compile(r"^[-_=]{2,}\s*$")
# Noise: CÔNG BÁO, số trang, footers
RE_NOISE  = re.compile(r"(CÔNG\s+BÁO.*$|^\s*Trang\s+\d+\s*$|^\s*\d+\s*/\s*\d+\s*$|\[\d+\])", re.MULTILINE)

# Từ khóa phân loại quy phạm (skill 02 mục 2.4)
NORM_KEYWORDS: dict[str, list[str]] = {
    "nghia_vu": [r"\bphải\b", r"có trách nhiệm", r"có nghĩa vụ", r"bắt buộc"],
    "quyen":    [r"có quyền", r"được phép", r"\bđược\b"],
    "cam_doan": [r"không được", r"\bcấm\b", r"nghiêm cấm", r"bị cấm"],
    "thu_tuc":  [r"thủ tục", r"trình tự", r"\bhồ sơ\b", r"quy trình"],
}


def classify_norm(text: str) -> str:
    """Gắn nhãn loại quy phạm: nghia_vu / quyen / cam_doan / thu_tuc / khac."""
    t = text.lower()
    for norm_type, patterns in NORM_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, t):
                return norm_type
    return "khac"


# ─── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DiemRecord:
    ky_hieu:  str
    noi_dung: str


@dataclass
class KhoanRecord:
    so:       int
    noi_dung: str
    diems:    list[dict] = field(default_factory=list)


@dataclass
class DieuRecord:
    """Một Điều luật với đầy đủ ngữ cảnh phân cấp (checklist 1.3)."""
    id:         str
    van_ban:    str
    slug:       str          # prefix ngắn dùng để tham chiếu nhanh
    so_dieu:    int
    tieu_de:    str
    phan:       str | None   # Phần (nếu có)
    chuong_so:  str | None   # Số Chương bằng chữ số La Mã / Ả Rập
    ten_chuong: str | None
    muc_so:     str | None   # Số Mục
    ten_muc:    str | None
    norm_type:  str          # nghia_vu / quyen / cam_doan / thu_tuc / khac
    noi_dung:   str          # toàn bộ text Điều (tiêu đề + thân)
    khoans:     list[dict] = field(default_factory=list)


# ─── Bước 1.4 — Chuẩn hóa text ────────────────────────────────────────────────

def normalize_text(raw: str) -> str:
    """
    Làm sạch text đã có sẵn (.txt):
      - Bỏ separator thuần (----, ____) và noise (CÔNG BÁO, số trang)
      - Chuẩn hóa dấu gạch ngang
      - Chuẩn hóa khoảng trắng thừa
      - Gộp ≥3 dòng trắng liên tiếp thành 1
    """
    # Bỏ noise trước khi tách dòng
    text = RE_NOISE.sub("", raw)

    cleaned: list[str] = []
    for line in text.splitlines():
        if RE_SEP.match(line.strip()):
            continue
        line = line.replace("–", "-").replace("—", "-")
        line = re.sub(r"[ \t]+", " ", line).rstrip()
        cleaned.append(line)

    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned))
    return result.strip()


# ─── Bước 1.3 — Parser Khoản / Điểm ──────────────────────────────────────────

def parse_khoans(body: str) -> list[dict]:
    """
    Phân tách Khoản và Điểm trong phần thân của một Điều.

    - Khoản : dòng bắt đầu bằng `<số>.  <text>` (không phải tiêu đề Điều)
    - Điểm  : dòng bắt đầu bằng `<chữ thường>)  <text>`
    """
    lines = body.splitlines()
    khoans:          list[KhoanRecord] = []
    cur_khoan:       KhoanRecord | None = None
    cur_diem_key:    str | None = None
    cur_diem_lines:  list[str] = []

    def flush_diem() -> None:
        nonlocal cur_diem_key, cur_diem_lines
        if cur_diem_key and cur_khoan is not None:
            cur_khoan.diems.append(
                asdict(DiemRecord(
                    ky_hieu=cur_diem_key,
                    noi_dung=" ".join(cur_diem_lines).strip(),
                ))
            )
        cur_diem_key = None
        cur_diem_lines = []

    for line in lines:
        stripped = line.strip()
        m_k = RE_KHOAN.match(stripped)
        m_d = RE_DIEM.match(stripped)

        if m_k and not RE_DIEU.match(stripped):
            flush_diem()
            if cur_khoan is not None:
                khoans.append(cur_khoan)
            cur_khoan = KhoanRecord(
                so=int(m_k.group(1)),
                noi_dung=m_k.group(2).strip(),
            )
        elif m_d and cur_khoan is not None:
            flush_diem()
            cur_diem_key = m_d.group(1)
            cur_diem_lines = [m_d.group(2).strip()]
        elif cur_diem_key is not None:
            if stripped:
                cur_diem_lines.append(stripped)
        elif cur_khoan is not None:
            if stripped:
                cur_khoan.noi_dung += " " + stripped
        # else: preamble text trước khoản đầu tiên → bỏ qua (đã có trong noi_dung Điều)

    flush_diem()
    if cur_khoan is not None:
        khoans.append(cur_khoan)

    return [asdict(k) for k in khoans]


# ─── Bước 1.3 — Parser phân cấp toàn văn bản ────────────────────────────────

def parse_document(text: str, van_ban_id: str, slug: str) -> list[DieuRecord]:
    """
    Quét toàn bộ văn bản, duy trì ngữ cảnh Phần/Chương/Mục,
    trả về danh sách DieuRecord (một phần tử = một Điều).
    """
    records: list[DieuRecord] = []

    cur_phan:       str | None = None
    cur_chuong_so:  str | None = None
    cur_ten_chuong: str | None = None
    cur_muc_so:     str | None = None
    cur_ten_muc:    str | None = None

    # Trạng thái "đang chờ tên" cho Chương / Mục
    pending_chuong: bool = False
    pending_muc:    bool = False

    cur_dieu_match: re.Match | None = None
    cur_dieu_lines: list[str] = []

    def flush_dieu() -> None:
        if cur_dieu_match is None:
            return
        num   = int(cur_dieu_match.group(1))
        title = cur_dieu_match.group(2).strip()
        body  = "\n".join(cur_dieu_lines).strip()
        full  = f"Điều {num}. {title}\n{body}" if title else f"Điều {num}\n{body}"
        khoans = parse_khoans(body)
        rec = DieuRecord(
            id=f"{slug}_Điều_{num}",
            van_ban=van_ban_id,
            slug=slug,
            so_dieu=num,
            tieu_de=title,
            phan=cur_phan,
            chuong_so=cur_chuong_so,
            ten_chuong=cur_ten_chuong,
            muc_so=cur_muc_so,
            ten_muc=cur_ten_muc,
            norm_type=classify_norm(full),
            noi_dung=full,
            khoans=khoans,
        )
        records.append(rec)

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()
        i += 1

        if not line:
            # Dòng trắng: nếu đang trong Điều thì giữ lại để không mất ngắt đoạn
            if cur_dieu_match is not None:
                cur_dieu_lines.append("")
            continue

        # ── Phần ────────────────────────────────────────────────────────────
        if RE_PHAN.match(line):
            flush_dieu()
            cur_dieu_match = None
            cur_dieu_lines = []
            cur_phan = line
            cur_chuong_so = None
            cur_ten_chuong = None
            cur_muc_so = None
            cur_ten_muc = None
            pending_chuong = False
            pending_muc = False
            continue

        # ── Chương ──────────────────────────────────────────────────────────
        m_ch = RE_CHUONG.match(line)
        if m_ch:
            flush_dieu()
            cur_dieu_match = None
            cur_dieu_lines = []
            cur_chuong_so  = m_ch.group(1)
            cur_ten_chuong = None
            cur_muc_so     = None
            cur_ten_muc    = None
            pending_chuong = True
            pending_muc    = False
            continue

        # ── Mục ─────────────────────────────────────────────────────────────
        m_muc = RE_MUC.match(line)
        if m_muc:
            flush_dieu()
            cur_dieu_match = None
            cur_dieu_lines = []
            cur_muc_so     = m_muc.group(1)
            cur_ten_muc    = None
            pending_muc    = True
            pending_chuong = False
            continue

        # ── Tên Chương (dòng đầu tiên không rỗng sau "Chương X") ────────────
        if pending_chuong and not RE_DIEU.match(line) and not RE_MUC.match(line):
            cur_ten_chuong = line
            pending_chuong = False
            continue

        # ── Tên Mục (dòng đầu tiên không rỗng sau "Mục X") ──────────────────
        if pending_muc and not RE_DIEU.match(line):
            cur_ten_muc = line
            pending_muc = False
            continue

        # ── Điều ─────────────────────────────────────────────────────────────
        m_d = RE_DIEU.match(line)
        if m_d:
            flush_dieu()
            cur_dieu_match = m_d
            cur_dieu_lines = []
            pending_chuong = False
            pending_muc    = False
            continue

        # ── Nội dung Điều ────────────────────────────────────────────────────
        if cur_dieu_match is not None:
            cur_dieu_lines.append(raw_line.rstrip())

    flush_dieu()
    return records


# ─── Pipeline chính ───────────────────────────────────────────────────────────

def process_file(src: Path, van_ban_id: str, slug: str) -> int:
    """Đọc, normalize, parse, ghi normalized + JSONL. Trả về số Điều."""
    raw  = src.read_text(encoding="utf-8")
    text = normalize_text(raw)

    # 1.4 — ghi normalized
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    norm_path = NORM_DIR / f"{slug}.txt"
    norm_path.write_text(text, encoding="utf-8")

    # 1.3 + 1.4 — parse + ghi JSONL
    records = parse_document(text, van_ban_id, slug)
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    chunk_path = CHUNK_DIR / f"{slug}.jsonl"
    with chunk_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    return len(records)


def write_metadata() -> None:
    """1.5 — ghi metadata.json."""
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(
        json.dumps(METADATA, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ metadata.json → {META_FILE.relative_to(REPO_ROOT)}  ({len(METADATA)} văn bản)")


# ─── Kiểm tra output ──────────────────────────────────────────────────────────

def verify() -> None:
    print("\n── Thống kê output ──────────────────────────────────────────────────")
    total_dieu   = 0
    total_khoans = 0
    total_diems  = 0

    for p in sorted(CHUNK_DIR.glob("*.jsonl")):
        lines = p.read_text(encoding="utf-8").splitlines()
        n_khoans = sum(
            len(json.loads(l).get("khoans", []))
            for l in lines
        )
        n_diems = sum(
            len(k.get("diems", []))
            for l in lines
            for k in json.loads(l).get("khoans", [])
        )
        total_dieu   += len(lines)
        total_khoans += n_khoans
        total_diems  += n_diems

        sample = json.loads(lines[0]) if lines else {}
        chuong = sample.get("chuong_so") or "-"
        muc    = sample.get("muc_so") or "-"
        norm   = sample.get("norm_type", "-")
        print(
            f"  {p.name:<30} {len(lines):>4} Điều  "
            f"{n_khoans:>5} Khoản  {n_diems:>5} Điểm  "
            f"(mẫu: Điều {sample.get('so_dieu','?')}, "
            f"Chương {chuong}, Mục {muc}, norm={norm})"
        )

    print(f"\n  Tổng: {total_dieu} Điều  {total_khoans} Khoản  {total_diems} Điểm")
    print(f"  Văn bản: {len(list(CHUNK_DIR.glob('*.jsonl')))}")

    print("\n── Metadata (1.5) ───────────────────────────────────────────────────")
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    for vid, m in meta.items():
        flag = "✅" if m["tinh_trang"] == "con_hieu_luc" else "⚠️ "
        print(
            f"  {flag} {vid:<25}  hiệu lực: {m['ngay_hieu_luc']}  "
            f"({m['ten'][:55]})"
        )

    print("\n── Kiểm tra mẫu phân cấp (1.3) ─────────────────────────────────────")
    bllđ = CHUNK_DIR / "BLLĐ_2019.jsonl"
    if bllđ.exists():
        recs = [json.loads(l) for l in bllđ.read_text(encoding="utf-8").splitlines()]
        # In 1 Điều có Khoản + Điểm
        for r in recs:
            if r.get("khoans") and any(k["diems"] for k in r["khoans"]):
                print(f"\n  Ví dụ Điều {r['so_dieu']} ({r['tieu_de']}) — Chương {r['chuong_so']} Mục {r['muc_so']}")
                for k in r["khoans"][:2]:
                    print(f"    Khoản {k['so']}: {k['noi_dung'][:80]}...")
                    for d in k["diems"][:3]:
                        print(f"      Điểm {d['ky_hieu']}): {d['noi_dung'][:70]}...")
                break


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Chuẩn hóa & phân tách văn bản Luật Lao động")
    ap.add_argument("--verify", action="store_true", help="In thống kê sau khi xử lý")
    ap.add_argument(
        "--only",
        metavar="FILE",
        help="Chỉ xử lý một file, ví dụ: --only BLLĐ-45-2019.txt",
    )
    args = ap.parse_args()

    if not SRC_DIR.exists():
        print(f"❌ Thư mục nguồn không tồn tại: {SRC_DIR}", file=sys.stderr)
        sys.exit(1)

    write_metadata()

    processed = 0
    for fname, (van_ban_id, slug) in FILE_MAP.items():
        if args.only and args.only not in fname:
            continue
        src = SRC_DIR / fname
        if not src.exists():
            print(f"⚠️  Bỏ qua (file chưa có): {src.name}")
            continue
        n = process_file(src, van_ban_id, slug)
        print(f"✅ {fname:<35} → {n:>4} Điều  [{slug}]")
        processed += 1

    if processed == 0:
        print("⚠️  Không có file nào được xử lý.")
        return

    print(f"\n✅ Hoàn thành {processed} văn bản → data/labor-law/")

    if args.verify:
        verify()


if __name__ == "__main__":
    main()

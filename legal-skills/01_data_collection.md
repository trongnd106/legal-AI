# Skill 01 — Thu thập & Chuẩn hóa dữ liệu Luật Lao động

> **Phủ checklist**: mục 1.1 · 1.2 · 1.3 · 1.4 · 1.5  
> **Repo path**: `data/labor-law/raw/` (tạo mới) và `scripts/01_prepare_data.py`

---

## Bước 1 — Tải văn bản gốc (1.1 + 1.2)

### Nguồn ưu tiên
| Văn bản | Số hiệu | URL tải trực tiếp |
|---------|---------|-------------------|
| Bộ luật Lao động 2019 | 45/2019/QH14 | https://vbpl.vn/botuphap/Pages/vbpq-van-ban-goc.aspx?ItemID=136064 |
| Nghị định 145/2020/NĐ-CP | 145/2020 | https://vbpl.vn/TW/Pages/vbpq-van-ban-goc.aspx?ItemID=148009 |
| Nghị định 12/2022/NĐ-CP | 12/2022 | https://vbpl.vn/TW/Pages/vbpq-van-ban-goc.aspx?ItemID=152468 |
| Nghị định 38/2022/NĐ-CP | 38/2022 | https://vbpl.vn/TW/Pages/vbpq-van-ban-goc.aspx?ItemID=153262 |

### Script tải tự động
```python
# scripts/01_download_raw.py
import requests, pathlib

DOCS = {
    "BLLĐ_2019": "https://vbpl.vn/...",   # thay bằng URL file Word/PDF
    "ND_145_2020": "...",
    "ND_12_2022": "...",
    "ND_38_2022": "...",
}
OUT = pathlib.Path("data/labor-law/raw")
OUT.mkdir(parents=True, exist_ok=True)

for name, url in DOCS.items():
    r = requests.get(url, timeout=30)
    (OUT / f"{name}.docx").write_bytes(r.content)
    print(f"✅ Downloaded {name}")
```

> **Thực tế**: vbpl.vn yêu cầu tải thủ công → tải file `.docx` hoặc `.pdf`, đặt vào `data/labor-law/raw/`.

---

## Bước 2 — Chuẩn hóa text (1.4)

### Chuyển đổi từ .docx / .pdf sang .txt thuần
```bash
# Dùng python-docx và pdfplumber — đã có trong pyproject.toml của GraphRAG
pip install python-docx pdfplumber
```

```python
# scripts/01_normalize_text.py
import pathlib, re
from docx import Document

RAW = pathlib.Path("data/labor-law/raw")
OUT = pathlib.Path("data/labor-law/normalized")
OUT.mkdir(parents=True, exist_ok=True)

def clean(text: str) -> str:
    # Xóa header/footer lặp lại
    text = re.sub(r"(Trang \d+|CÔNG BÁO.*?\n)", "", text)
    # Chuẩn hóa dấu gạch đầu dòng
    text = re.sub(r"[–—]", "-", text)
    # Chuẩn hóa khoảng trắng
    text = re.sub(r" +", " ", text)
    return text.strip()

for f in RAW.glob("*.docx"):
    doc = Document(f)
    full = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    (OUT / f.stem).with_suffix(".txt").write_text(clean(full), encoding="utf-8")
    print(f"✅ Normalized {f.name}")
```

---

## Bước 3 — Tách file theo Điều (1.3 + 1.4)

GraphRAG hoạt động tốt hơn khi mỗi chunk là một đơn vị pháp lý độc lập. Tách theo **Điều** để đảm bảo không bị cắt giữa quy phạm.

```python
# scripts/01_split_by_dieu.py
import re, pathlib, json

SRC = pathlib.Path("data/labor-law/normalized/BLLĐ_2019.txt")
OUT_DIR = pathlib.Path("data/labor-law/chunks")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DIEU_PATTERN = re.compile(r"(Điều\s+\d+[\.\:]\s+.+?)(?=Điều\s+\d+[\.\:]|\Z)", re.DOTALL)

text = SRC.read_text(encoding="utf-8")
articles = DIEU_PATTERN.findall(text)

records = []
for i, art in enumerate(articles):
    match = re.match(r"Điều\s+(\d+)[\.\:]\s+(.+?)[\n\r]", art)
    if not match:
        continue
    num, title = match.group(1), match.group(2).strip()
    records.append({
        "id": f"BLLĐ_2019_Điều_{num}",
        "so_dieu": int(num),
        "tieu_de": title,
        "noi_dung": art.strip(),
        "van_ban": "45/2019/QH14",
    })

# Lưu JSONL để GraphRAG đọc
with open(OUT_DIR / "BLLĐ_2019.jsonl", "w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"✅ Tách được {len(records)} Điều")
```

---

## Bước 4 — Xây dựng metadata mapping (1.5)

```python
# data/labor-law/metadata.json
{
  "45/2019/QH14": {
    "ten": "Bộ luật Lao động 2019",
    "loai": "bo_luat",
    "ngay_ban_hanh": "2019-11-20",
    "ngay_hieu_luc": "2021-01-01",
    "tinh_trang": "con_hieu_luc",
    "pham_vi": "toan_quoc",
    "co_quan": "Quoc hoi"
  },
  "145/2020/NĐ-CP": {
    "ten": "Nghị định 145/2020/NĐ-CP",
    "loai": "nghi_dinh",
    "ngay_ban_hanh": "2020-12-14",
    "ngay_hieu_luc": "2021-02-01",
    "tinh_trang": "con_hieu_luc",
    "pham_vi": "toan_quoc",
    "co_quan": "Chinh phu",
    "huong_dan_cho": "45/2019/QH14"
  }
}
```

---

## Kiểm tra hoàn thành

```bash
# Chạy toàn bộ pipeline thu thập
python scripts/01_download_raw.py      # → data/labor-law/raw/*.docx
python scripts/01_normalize_text.py   # → data/labor-law/normalized/*.txt
python scripts/01_split_by_dieu.py    # → data/labor-law/chunks/*.jsonl

# Kiểm tra output
ls -lh data/labor-law/chunks/
python -c "
import json
lines = open('data/labor-law/chunks/BLLĐ_2019.jsonl').readlines()
print(f'Tổng số Điều: {len(lines)}')
print(json.loads(lines[0]))
"
```

**Kết quả mong đợi**: ~220 Điều cho BLLĐ 2019, mỗi dòng JSONL có đủ `id`, `so_dieu`, `noi_dung`, `van_ban`.

---

## Cấu trúc thư mục sau khi hoàn thành

```
data/labor-law/
├── raw/                    # File gốc tải về (.docx / .pdf)
│   ├── BLLĐ_2019.docx
│   ├── ND_145_2020.docx
│   └── ...
├── normalized/             # Text UTF-8 đã làm sạch
│   ├── BLLĐ_2019.txt
│   └── ...
├── chunks/                 # JSONL tách theo Điều — đầu vào cho GraphRAG
│   ├── BLLĐ_2019.jsonl
│   └── ...
└── metadata.json           # Thông tin hiệu lực từng văn bản
```
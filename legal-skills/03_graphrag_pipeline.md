# Skill 03 — Xây dựng Knowledge Graph với GraphRAG

> **Phủ checklist**: mục 3.1 · 3.2 · 3.3 · 3.4 · 3.5 · 3.6 · 3.7  
> **Repo path**: `data/labor-law/` · `graphrag` CLI

---

## Yêu cầu môi trường

```bash
# Repo dùng uv (xem pyproject.toml)
uv sync
# Hoặc dùng pip truyền thống
pip install graphrag

# Kiểm tra version
graphrag --version   # nên >= 1.0.0
```

Thiết lập biến môi trường (copy từ `.env.examples`):
```bash
cp .env.examples .env
# Điền vào .env:
# GRAPHRAG_API_KEY=<your-openai-key>
# GRAPHRAG_API_BASE=https://api.openai.com/v1
# GRAPHRAG_LLM_MODEL=gpt-4o-mini   # dùng mini để tiết kiệm chi phí khi test
```

---

## Bước 1 — Khởi tạo project (3.1)

```bash
# Tạo thư mục workspace riêng cho luật lao động
graphrag init --root data/labor-law

# Cấu trúc được tạo ra:
# data/labor-law/
# ├── settings.yaml        ← chỉnh theo skill 02
# ├── .env                 ← API key
# ├── prompts/             ← thay bằng prompts tiếng Việt (skill 02)
# └── input/               ← copy chunks/*.jsonl vào đây
```

```bash
# Copy dữ liệu vào input/
cp data/labor-law/chunks/*.jsonl data/labor-law/input/
```

---

## Bước 2 — Tùy chỉnh prompt entity extraction (3.2)

GraphRAG hỗ trợ **auto prompt tuning** — nên chạy trước khi index toàn bộ:

```bash
# Auto-tune prompts dựa trên 5 sample chunks
graphrag prompt-tune \
  --root data/labor-law \
  --language Vietnamese \
  --domain "Vietnamese Labor Law" \
  --output data/labor-law/prompts \
  --limit 5
```

Sau đó mở `data/labor-law/prompts/entity_extraction.txt` và **thêm thủ công** các entity đặc thù lao động từ skill 02 vào phần `-Entity Types-`.

Kiểm tra prompt có nhận diện đúng:
```bash
# Test extraction trên 1 đoạn
python -c "
from graphrag.index.operations.extract_entities import extract_entities
# xem docs tại https://microsoft.github.io/graphrag/prompt_tuning/
"
```

---

## Bước 3 — Tùy chỉnh prompt relationship extraction (3.3)

Mở `data/labor-law/prompts/relationship_extraction.txt`, thêm vào phần hướng dẫn:

```
Chú ý các loại quan hệ đặc thù pháp luật lao động:
- cites: khi điều khoản dẫn chiếu đến điều/nghị định khác ("theo quy định tại Điều X")
- amends: khi nghị định sửa đổi nội dung bộ luật
- obligates: khi quy định áp đặt nghĩa vụ ("phải", "có trách nhiệm")
- prohibits: khi quy định cấm hành vi ("không được", "cấm", "nghiêm cấm")
- entitles: khi quy định trao quyền ("có quyền", "được phép")
- penalizes: khi điều khoản quy định chế tài/xử phạt
```

---

## Bước 4 — Cấu hình chunking (3.4)

Trong `settings.yaml`, đảm bảo chunking không cắt giữa Khoản:

```yaml
chunks:
  size: 600           # ~1-2 Khoản
  overlap: 80
  group_by_columns:
    - van_ban         # Không trộn chunk từ 2 văn bản khác nhau
  encoding_model: cl100k_base
```

Nếu muốn tách sẵn theo Khoản (khuyến nghị — độ chính xác cao hơn):
```python
# scripts/03_split_by_khoan.py
import re, json, pathlib

def split_khoan(dieu_text: str, dieu_id: str) -> list:
    """Tách Điều thành các Khoản riêng."""
    khoan_pattern = re.compile(r"(\d+\.\s+.+?)(?=\d+\.\s+|\Z)", re.DOTALL)
    khoans = khoan_pattern.findall(dieu_text)
    results = []
    for i, k in enumerate(khoans, 1):
        results.append({
            "id": f"{dieu_id}_Khoản_{i}",
            "so_khoan": i,
            "noi_dung": k.strip(),
            "parent_dieu": dieu_id,
        })
    return results if results else [{"id": dieu_id, "noi_dung": dieu_text}]
```

---

## Bước 5 — Chạy indexing pipeline (3.5)

```bash
# Chạy index — LƯU Ý: tốn tokens, test với 10 file trước
graphrag index --root data/labor-law

# Theo dõi tiến độ
# GraphRAG log vào stdout, có thể redirect:
graphrag index --root data/labor-law 2>&1 | tee logs/indexing_$(date +%Y%m%d).log
```

**Ước tính chi phí** (gpt-4o-mini):
- BLLĐ 2019 (~220 Điều × ~500 tokens) ≈ ~110K tokens
- 4 văn bản tổng cộng ≈ ~400–600K tokens input
- Chi phí ≈ $0.5–$1.0 với gpt-4o-mini

---

## Bước 6 — Kiểm tra output (3.6)

```bash
# Output nằm tại data/labor-law/output/
ls data/labor-law/output/

# Các file quan trọng:
# entities.parquet          — danh sách thực thể
# relationships.parquet     — danh sách quan hệ
# communities.parquet       — cụm tri thức
# community_reports.parquet — báo cáo tổng hợp theo cụm
# text_units.parquet        — các chunk đã index
```

```python
# scripts/03_inspect_output.py
import pandas as pd

entities = pd.read_parquet("data/labor-law/output/entities.parquet")
rels = pd.read_parquet("data/labor-law/output/relationships.parquet")

print(f"Tổng entity: {len(entities)}")
print(f"Tổng relationship: {len(rels)}")
print("\nEntity types:")
print(entities["type"].value_counts())
print("\nRelationship types:")
print(rels["relationship_type"].value_counts() if "relationship_type" in rels.columns else rels.head())
```

**Kết quả mong đợi:**
- ≥ 500 entities (BLLĐ 2019 đủ)
- ≥ 800 relationships
- Có đủ các type: `Dieu`, `ChuThe`, `HanhVi`, `HopDongLaoDong`...

---

## Bước 7 — Mô hình hóa dẫn chiếu chéo giữa BLLĐ và Nghị định (3.7)

GraphRAG tự phát hiện quan hệ `cites` nếu text có dạng "theo quy định tại Điều X Luật Y". Tuy nhiên nên **thêm thủ công** các liên kết quan trọng:

```python
# scripts/03_add_cross_references.py
"""
Thêm quan hệ guided_by giữa Nghị định và BLLĐ vào relationships.parquet
"""
import pandas as pd

rels = pd.read_parquet("data/labor-law/output/relationships.parquet")

# Thêm quan hệ hướng dẫn
extra = pd.DataFrame([
    {
        "source": "145/2020/NĐ-CP",
        "target": "45/2019/QH14",
        "description": "Nghị định 145/2020 hướng dẫn thi hành một số điều của BLLĐ 2019",
        "weight": 10.0,
        "combined_degree": 2,
    },
    {
        "source": "12/2022/NĐ-CP",
        "target": "45/2019/QH14",
        "description": "Nghị định 12/2022 quy định xử phạt vi phạm hành chính trong lĩnh vực lao động",
        "weight": 10.0,
        "combined_degree": 2,
    },
])

rels = pd.concat([rels, extra], ignore_index=True)
rels.to_parquet("data/labor-law/output/relationships.parquet", index=False)
print("✅ Đã thêm quan hệ dẫn chiếu chéo")
```

---

## Kiểm tra hoàn thành toàn bộ phần 3

```bash
# Quick sanity check
python scripts/03_inspect_output.py

# Kiểm tra community reports (quan trọng cho Global Search)
python -c "
import pandas as pd
cr = pd.read_parquet('data/labor-law/output/community_reports.parquet')
print(f'Tổng cộng {len(cr)} communities')
print(cr[['title','rank']].sort_values('rank', ascending=False).head(10))
"
```
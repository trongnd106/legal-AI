# Skill 03 — Xây dựng Knowledge Graph với GraphRAG

> **Phủ checklist**: mục 3.1 · 3.2 · 3.3 · 3.4 · 3.5 · 3.6 · 3.7  
> **Repo path**: `data/labor-law/` · `.venv/bin/graphrag` CLI  
> **Phụ thuộc**: Skill 01 (`scripts/01_prepare_data.py`) · Skill 02 (`data/labor-law/settings.yaml`, `prompts/`)

---

## Yêu cầu môi trường

```bash
# Repo dùng uv — venv đã có sẵn tại .venv/
uv sync

# Kiểm tra graphrag CLI
.venv/bin/graphrag --help   # phải hiện: init, index, update, prompt-tune, query
```

Thiết lập API key:
```bash
# Tạo file .env trong data/labor-law/
cat > data/labor-law/.env << 'EOF'
GRAPHRAG_API_KEY=<your-openai-or-compatible-key>
EOF
```

---

## Bước 1 — Khởi tạo project (3.1)

`graphrag init` sinh ra cấu trúc thư mục và `settings.yaml` mặc định. Vì Skill 02 đã tạo `settings.yaml` + prompts tùy chỉnh, chỉ cần init để sinh các file còn thiếu:

```bash
# Init — sinh prompts mặc định và .env mẫu (KHÔNG ghi đè settings.yaml đã có)
.venv/bin/graphrag init --root data/labor-law

# Cấu trúc sau init:
# data/labor-law/
# ├── settings.yaml        ← đã có từ Skill 02, GIỮ NGUYÊN
# ├── .env                 ← điền GRAPHRAG_API_KEY vào đây
# ├── prompts/
# │   ├── extract_graph.txt              ← prompt tiếng Việt (Skill 02)
# │   ├── community_report_labor.txt     ← prompt tiếng Việt (Skill 02)
# │   ├── summarize_descriptions.txt     ← sinh bởi init, dùng default
# │   ├── local_search_system_prompt.txt ← sinh bởi init
# │   └── ...
# ├── chunks/              ← JSONL đã có từ Skill 01
# ├── cache/               ← LLM cache, tồn tại qua nhiều lần chạy
# └── output/              ← kết quả indexing
```

> **Lưu ý:** `input_storage.base_dir: "chunks"` trong `settings.yaml` trỏ thẳng đến `data/labor-law/chunks/`.  
> **Không cần** copy JSONL vào `input/`.

---

## Bước 2 — Tùy chỉnh prompt entity + relationship extraction (3.2 · 3.3)

GraphRAG dùng **một prompt duy nhất** (`extract_graph.txt`) cho cả entity và relationship extraction — không có file riêng cho relationship.

Prompt `data/labor-law/prompts/extract_graph.txt` (đã tạo ở Skill 02) bao gồm:
- Hướng dẫn domain luật lao động tiếng Việt
- 13 entity types Tier 1 (inject qua `{entity_types}` từ `settings.yaml`)
- Quy tắc phân loại (`penalizes` vs `disciplines`, `TienLuong` vs `TraLuong`…)
- 3 ví dụ thực tế (Điều 35, Điều 38 NĐ 12/2022, Điều 125)
- 9 relation types với từ khóa nhận dạng

**Auto prompt-tune** (tuỳ chọn — dùng nếu muốn GraphRAG tự sinh ví dụ từ corpus):

```bash
# Sinh lại extract_graph.txt từ 5 sample chunks
# LƯU Ý: sẽ GHI ĐÈ prompts/extract_graph.txt — backup trước
cp data/labor-law/prompts/extract_graph.txt data/labor-law/prompts/extract_graph.txt.bak

.venv/bin/graphrag prompt-tune \
  --root data/labor-law \
  --language Vietnamese \
  --domain "Vietnamese Labor Law" \
  --output data/labor-law/prompts \
  --limit 5 \
  --no-discover-entity-types  # giữ entity_types từ settings.yaml, không tự sinh
```

> Auto-tune sinh ra: `extract_graph.txt`, `summarize_descriptions.txt`, `community_report_graph.txt`  
> Sau khi tune xong, cần thêm lại các quy tắc domain (penalizes/disciplines…) vì auto-tune không biết ontology Skill 02.

---

## Bước 3 — Cấu hình chunking (3.4)

`settings.yaml` đã cấu hình (Skill 02):

```yaml
chunking:
  size: 4000    # 1 Điều = 1 chunk, không cắt giữa Khoản
  overlap: 0    # Điều là unit pháp lý độc lập
```

`input.text_column: noi_dung` → GraphRAG đọc field `noi_dung` của JSONL làm text gửi vào LLM.  
Các field còn lại (`id`, `van_ban`, `so_dieu`, `norm_type`…) lưu trong `raw_data` của document và có thể dùng khi query.

> Skill 01 đã tách sẵn mỗi Điều thành 1 JSONL record — không cần script `split_by_khoan` thêm.

---

## Bước 4 — Chạy indexing pipeline (3.5)

```bash
# Test nhỏ trước — chỉ chạy 1 file (~80 Điều BLLĐ, ~800-1000 LLM requests)
# Tạm thời move các file khác ra ngoài:
mkdir -p data/labor-law/chunks_bak
mv data/labor-law/chunks/ND_*.jsonl data/labor-law/chunks_bak/
mv data/labor-law/chunks/TT_*.jsonl data/labor-law/chunks_bak/
mv data/labor-law/chunks/VBHN_*.jsonl data/labor-law/chunks_bak/

.venv/bin/graphrag index --root data/labor-law 2>&1 | tee logs/index_bllđ_$(date +%Y%m%d).log

# Khôi phục sau khi test OK
mv data/labor-law/chunks_bak/*.jsonl data/labor-law/chunks/
```

```bash
# Chạy full index — tất cả 7 văn bản (581 Điều)
.venv/bin/graphrag index --root data/labor-law 2>&1 | tee logs/index_full_$(date +%Y%m%d).log
```

**Ước tính thực tế** (gpt-4o-mini, `max_gleanings: 1`):

| Bước pipeline | LLM requests | Token ước tính |
|---------------|-------------|----------------|
| `extract_graph` (581 chunks × 2 calls) | ~1.160 | ~6M |
| `summarize_descriptions` | ~2.000–3.000 | ~3–4M |
| `create_community_reports` | ~100–200 | ~1M |
| **Tổng completion LLM** | **~4.000–5.000** | **~10–12M** |
| Embeddings | ~581 | ~0.4M |
| **Chi phí gpt-4o-mini** | | **~$3–5** |

**Chạy nhiều ngày trên free tier (Gemini/OpenRouter):**
- Cache LLM lưu tại `data/labor-law/cache/` — **giữ qua lần chạy lại**
- Ngày sau chạy lại: chunk đã cache → hit cache (0 token), chunk chưa cache → gọi API tiếp
- Gemini Flash free: ~1.500 req/ngày → full index cần ~3–4 ngày
- **KHÔNG xóa** `cache/` giữa các lần chạy

---

## Bước 5 — Kiểm tra output (3.6)

Output nằm tại:
```
data/labor-law/output/<timestamp>/artifacts/
```

Các file parquet quan trọng:

```bash
ls data/labor-law/output/*/artifacts/*.parquet
# create_final_entities.parquet
# create_final_relationships.parquet
# create_final_communities.parquet
# create_final_community_reports.parquet
# create_final_text_units.parquet
# create_final_documents.parquet
```

```python
# scripts/03_inspect_output.py
import pandas as pd
from pathlib import Path

# Tìm artifacts mới nhất
artifacts = sorted(Path("data/labor-law/output").glob("*/artifacts"))[-1]

entities = pd.read_parquet(artifacts / "create_final_entities.parquet")
rels     = pd.read_parquet(artifacts / "create_final_relationships.parquet")

print(f"Tổng entity: {len(entities)}")
print(f"Tổng relationship: {len(rels)}")

print("\nEntity types:")
if "type" in entities.columns:
    print(entities["type"].value_counts())

print("\nRelationship descriptions (top 15):")
if "description" in rels.columns:
    print(rels["description"].value_counts().head(15))
```

**Kết quả mong đợi sau full index:**
- ≥ 600 L2 entities (`ChuThe`, `HanhVi`, `CheTai`…)
- ≥ 1.000 L2 relationships
- Có đủ các type: `ChuThe`, `HanhVi`, `CheTai`, `XuLyKyLuat`, `CheDoBaoHiem`…

```bash
# Kiểm tra community reports (quan trọng cho Global Search)
python3 -c "
import pandas as pd
from pathlib import Path
artifacts = sorted(Path('data/labor-law/output').glob('*/artifacts'))[-1]
cr = pd.read_parquet(artifacts / 'create_final_community_reports.parquet')
print(f'Tổng cộng {len(cr)} communities')
if 'rank' in cr.columns:
    print(cr[['title','rank']].sort_values('rank', ascending=False).head(10))
else:
    print(cr[['title']].head(10))
"
```

---

## Bước 6 — Merge L1 structural graph (3.7)

Sau khi `graphrag index` xong, chạy script merge để gộp L1 (VanBan, Dieu, Khoan…) vào graph:

```bash
python3 scripts/02_merge_structural_graph.py --dry-run   # kiểm tra trước
python3 scripts/02_merge_structural_graph.py             # ghi merged_*.parquet
```

Output: `data/labor-law/output/merged_entities.parquet`, `merged_relationships.parquet`

Quan hệ dẫn chiếu chéo BLLĐ ↔ Nghị định đã được build tự động từ `metadata.json`:
- `guided_by`: NĐ hướng dẫn → BLLĐ
- `issued_by`: VanBan → CoQuan ban hành
- `cites`: dẫn chiếu chéo (resolve qua alias index)

---

## Kiểm tra hoàn thành toàn bộ phần 3

```bash
mkdir -p logs

# 1. Verify dữ liệu đầu vào (Skill 01)
python3 scripts/01_prepare_data.py --verify

# 2. Chạy index
.venv/bin/graphrag index --root data/labor-law 2>&1 | tee logs/index_$(date +%Y%m%d).log

# 3. Inspect L2 output
python3 scripts/03_inspect_output.py

# 4. Merge L1 + L2
python3 scripts/02_merge_structural_graph.py

# 5. Kiểm tra alias index không collision
python3 scripts/02_merge_structural_graph.py --verify
```

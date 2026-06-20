# Hướng dẫn đánh giá thực nghiệm — Chương 4

Tài liệu này mô tả cách thiết kế test case, chạy thí nghiệm và thu số liệu điền vào các bảng kết quả trong `Chuong/4_Ket_qua_thuc_nghiem.tex`.

---

## 1. Tổng quan

Chương 4 đánh giá hệ thống theo **bốn khía cạnh**:

1. Chất lượng câu trả lời (KwAcc, CiteAcc, ChainHit)
2. So sánh 5 phương pháp truy vấn (Zero-shot, Basic, Local, Global, Local+Multi-hop)
3. Module phân tích hợp đồng lao động (E6)
4. Hiệu năng indexing và latency truy vấn

**Tập đánh giá chính:** 10 test case domain `lao_dong` (corpus đã index đầy đủ).

**Không dùng cho kết luận chính:** các test case `dan_su`, `hinh_su`, `doanh_nghiep` (corpus chưa index) — chỉ phục vụ kiểm tra negative case / hallucination khi hỏi ngoài phạm vi tri thức.

---

## 2. Chuẩn bị môi trường

### 2.1. Yêu cầu

- GraphRAG đã index xong (`data/labor-law/output/` có file parquet)
- Python 3.11+
- API key OpenRouter

### 2.2. Cài đặt

```bash
cd /home/trong/Documents/graphrag
pip install openai tqdm python-dotenv
```

### 2.3. Kiểm tra artifacts

```bash
ls data/labor-law/output/*/artifacts/create_final_entities.parquet
# hoặc
ls data/labor-law/output/create_final_entities.parquet
```

### 2.4. Biến môi trường

Tạo file `.env` ở thư mục gốc repo:

```env
OPENROUTER_API_KEY=sk-or-v1-...
EVAL_LLM_MODEL=qwen/qwen3-235b-a22b-2507
```

---

## 3. Cấu trúc test case

Test cases nằm trong `tests/evaluation_suite.py`, hằng số `TEST_CASES`.

### 3.1. Các trường bắt buộc

| Trường | Ý nghĩa |
|--------|---------|
| `id` | Mã định danh (ví dụ: `LD001`) |
| `domain` | `lao_dong`, `dan_su`, `hinh_su`, ... |
| `category` | `single_hop`, `multi_hop`, `temporal`, `cross_domain` |
| `difficulty` | `easy`, `medium`, `hard` |
| `question` | Câu hỏi tiếng Việt |
| `expected_keywords` | Danh sách cụm từ **bắt buộc** xuất hiện trong câu trả lời |
| `expected_citations` | Điều/văn bản cần trích dẫn; `[]` nếu không yêu cầu cite cụ thể |
| `reasoning_chain` | (Tuỳ chọn, multi-hop) Chuỗi suy luận mong đợi |

### 3.2. Bộ 10 câu `lao_dong` (tập đánh giá chính — E1)

| ID | Loại | Độ khó | Mô tả |
|----|------|--------|-------|
| LD001 | single_hop | easy | Số ngày nghỉ phép tối thiểu → Điều 113 |
| LD002 | single_hop | easy | Lương tối thiểu vùng I → Điều 91 |
| LD003 | single_hop | easy | Thời gian thử việc → Điều 27 |
| LD004 | single_hop | medium | Số lần ký HĐLĐ → Điều 20 |
| LD013 | single_hop | medium | Số ngày nghỉ kết hôn → Điều 115 |
| LD010 | multi_hop | medium | Không trả trợ cấp thôi việc → Điều 46 → NĐ 12/2022 |
| LD011 | multi_hop | hard | Đơn phương chấm dứt → Điều 35 → Điều 46 |
| LD012 | multi_hop | hard | Lương dưới tối thiểu → Điều 90 → NĐ 12/2022 |
| TMP001 | temporal | medium | NĐ lương tối thiểu đang hiệu lực → NĐ 74/2024 |
| TMP002 | temporal | medium | NĐ 90/2019 còn hiệu lực không? |

### 3.3. Cách thêm test case mới

Thêm vào `TEST_CASES` trong `tests/evaluation_suite.py`:

```python
{
    "id": "LD014",
    "domain": "lao_dong",
    "category": "single_hop",       # single_hop | multi_hop | temporal | cross_domain
    "difficulty": "easy",           # easy | medium | hard
    "question": "Câu hỏi của bạn?",
    "expected_keywords": [          # TẤT CẢ từ này PHẢI xuất hiện trong câu trả lời
        "từ khoá 1",
        "Điều XX",
    ],
    "expected_citations": ["Điều XX"],  # [] nếu không yêu cầu cite cụ thể
    # Chỉ cần với multi_hop:
    "reasoning_chain": "Điều A (lý do) → Điều B (hậu quả)",
},
```

### 3.4. Nguyên tắc viết `expected_keywords`

- Dùng **cụm từ pháp lý đặc thù** (con số, tên Điều), tránh từ chung chung
- Giữ 3–4 từ khoá để giảm false negative khi LLM diễn đạt khác
- Ví dụ tốt: `["12 ngày", "Điều 113"]`
- Ví dụ kém: `["nghỉ phép", "hàng năm"]` — quá chung

### 3.5. Công thức chỉ số (tự động trong `evaluate_system`)

**Keyword Accuracy (KwAcc):**

\[
\mathrm{KwAcc} = \frac{|\{tc \mid \forall kw \in expected\_keywords: kw \subseteq answer\}|}{|T|}
\]

**Citation Accuracy (CiteAcc):** chỉ tính trên các test case có `expected_citations` khác rỗng.

**Reasoning Chain Hit (ChainHit):** đánh giá thủ công — kiểm tra câu trả lời có đề cập đủ các Điều trong `reasoning_chain`.

---

## 4. Năm phương pháp so sánh

| Mã | Phương pháp | Mô tả ngắn |
|----|-------------|-------------|
| BL0 | Zero-shot LLM | Gọi LLM trực tiếp, không retrieval |
| BL1 | Basic Search | Vector/keyword trên text units, không graph |
| — | Local Search | GraphRAG entity-centric (`query/local_search.py`) |
| — | Global Search | Map-reduce trên community reports |
| — | Local + Multi-hop | Local Search + `VNLegalReasoningEngine` |

Script đánh giá: `scripts/run_evaluation.py`.

---

## 5. Chạy thu số liệu

### 5.1. Lệnh chạy chính

```bash
cd /home/trong/Documents/graphrag
python3 scripts/run_evaluation.py
```

Script sẽ:

1. Lọc 10 test case `domain == "lao_dong"`
2. Chạy lần lượt 5 phương pháp
3. Tính KwAcc, CiteAcc theo category
4. Đo latency P50/P95 (5 lần lặp × 5 câu đại diện)
5. Ghi kết quả ra thư mục `results/`

### 5.2. Đầu ra

| File | Nội dung |
|------|----------|
| `results/eval_results.json` | Log chi tiết từng câu, từng phương pháp |
| `results/latex_numbers.txt` | Macro LaTeX sẵn sàng dán vào báo cáo |
| Terminal | Bảng tóm tắt copy trực tiếp |

Ví dụ output terminal:

```
BẢN TÓM TẮT KẾT QUẢ (điền vào Bảng table:overall_comparison)
================================================================
Phương pháp           KwAcc     CiteAcc     P50(ms)    P95(ms)
-----------------------------------------------------------------
Zero-shot LLM       40% (4/10)     30%        800      1,500
Basic Search        60% (6/10)     70%      1,200      2,500
Local Search        90% (9/10)     88%      2,500      8,000
Global Search       80% (8/10)     75%      8,000     25,000
Local+Multihop     100%(10/10)     92%      3,500     12,000
```

### 5.3. Chạy từng phương pháp riêng (debug)

```python
from tests.evaluation_suite import TEST_CASES, evaluate_system
from query.loader import GraphLoader

LAO_DONG = [tc for tc in TEST_CASES if tc["domain"] == "lao_dong"]
loader = GraphLoader("data/labor-law").load()

# Ví dụ: chỉ Local Search
from scripts.run_evaluation import _make_answer_fn_local
answer_fn = _make_answer_fn_local(loader)
results = evaluate_system(answer_fn, test_cases=LAO_DONG)
print(results["keyword_accuracy"], results["citation_accuracy"])
```

---

## 6. Điền số liệu vào các bảng LaTeX

> **Lưu ý:** Các con số trong `4_Ket_qua_thuc_nghiem.tex` hiện tại (40%, 90%, 100%, ...) là **ước tính minh họa**. Sau khi chạy `run_evaluation.py`, thay bằng số **thực đo** từ `results/eval_results.json`.

### 6.1. Bảng `table:test_cases`

Chỉ liệt kê **10 câu `lao_dong`** là tập chính. Các domain khác (nếu giữ) ghi rõ: *corpus chưa index — negative case*.

### 6.2. Bảng `table:overall_comparison` (E1, n = 10)

| Cột | Nguồn JSON |
|-----|------------|
| KwAcc | `keyword_accuracy`, `kw_hits`, `total` |
| CiteAcc | `citation_accuracy` (chỉ trên mẫu có `expected_citations`) |
| Ghi chú | Đọc `details[]` — các câu fail |

### 6.3. Bảng `table:by_category`

Lấy từ `by_category` của **Local Search** và **Local+Multihop**:

```json
"by_category": {
  "single_hop": {"total": 5, "keyword_hits": 5, ...},
  "multi_hop":  {"total": 3, "keyword_hits": 1, ...},
  "temporal":   {"total": 2, "keyword_hits": 2, ...}
}
```

Tính: `keyword_hits / total` cho từng category.

### 6.4. Bảng `table:latency`

| Cột | Nguồn JSON |
|-----|------------|
| P50 (ms) | `latency_p50_ms` |
| P95 (ms) | `latency_p95_ms` |
| LLM calls/query | Ước lượng: BL0/BL1 = 1; Local = 1–2; Global = 5–15 |

### 6.5. Bảng `table:indexing_stats`

Chạy script kiểm tra output:

```bash
python3 scripts/03_inspect_output.py
```

Hoặc đọc parquet trực tiếp:

```python
import pandas as pd
from pathlib import Path

out = Path("data/labor-law/output")
# Đường dẫn có thể là out/ hoặc out/*/artifacts/ tùy phiên bản GraphRAG
entities = pd.read_parquet(list(out.rglob("create_final_entities.parquet"))[0])
rels     = pd.read_parquet(list(out.rglob("create_final_relationships.parquet"))[0])
comms    = pd.read_parquet(list(out.rglob("create_final_communities.parquet"))[0])

print(f"Entities L2: {len(entities)}")
print(f"Relationships L2: {len(rels)}")
print(f"Communities: {comms['community'].nunique() if 'community' in comms.columns else len(comms)}")
```

Merged graph (L1+L2) nằm ở `data/labor-law/output/merged_entities.parquet` (sau `02_merge_structural_graph.py`).

Thời gian indexing: ghi lại wall time khi chạy `graphrag index --root data/labor-law`.

### 6.6. Bảng `table:contract_case` (E6)

Gọi API phân tích HĐLĐ mẫu:

```bash
# Khởi động API trước
uvicorn api.main:app --reload --port 8000

# Gửi file HĐLĐ mẫu (DOCX)
curl -X POST "http://localhost:8000/api/contract/analyze" \
  -F "file=@path/to/hop_dong_mau.docx"
```

Điền: điểm tuân thủ, số vi phạm VRxxx, thời gian xử lý từ response JSON.

### 6.7. Case study (LD003, LD011, LD012)

Sau khi chạy evaluation, mở `results/eval_results.json` → `details` → copy câu trả lời thực tế vào khối `\begin{example}...` trong LaTeX. Ghi rõ `kw_hit`, `cite_hit` từ trường `kw_hit`, `cite_hit` trong JSON.

---

## 7. Ánh xạ kịch bản E1–E6

| Kịch bản | Test cases | So sánh |
|----------|------------|---------|
| E1 | 10 câu `lao_dong` | BL0, BL1, Local, Global, Multihop |
| E2 | 5 câu `single_hop` | BL1 vs Local |
| E3 | 2 câu tổng hợp (tuỳ chọn) | Local vs Global |
| E4 | 3 câu `multi_hop` (LD010–012) | Local vs Local+Multihop |
| E5 | 2 câu `temporal` (TMP001–002) | Local vs Local + temporal filter |
| E6 | 1 file HĐLĐ mẫu | Rule validator |

---

## 8. Domain ngoài `lao_dong` — cách dùng đúng

**Không** đưa `dan_su`, `hinh_su`, `doanh_nghiep` vào bảng kết quả chính như thể đã đánh giá đầy đủ.

**Nên:**

- Chạy riêng 12 câu ngoài corpus để kiểm tra hệ thống có từ chối / không hallucinate
- Ghi trong phần *Hạn chế*: accuracy thấp là **dự kiến**
- Nếu cần mở rộng: index thêm corpus tương ứng rồi mới đưa vào E1

---

## 9. Checklist trước khi nộp báo cáo

- [ ] Đã chạy `python3 scripts/run_evaluation.py` với API key hợp lệ
- [ ] Đã thay số ước tính trong bảng bằng số từ `results/eval_results.json`
- [ ] Case study dùng câu trả lời **thực tế**, không viết tay
- [ ] Bảng indexing stats khớp với parquet thực tế
- [ ] E6 đã chạy trên file HĐLĐ mẫu thật
- [ ] Phần hạn chế nêu rõ: n = 10, chưa review luật sư, RAGAS chưa chạy đủ

---

## 10. Tài liệu liên quan

| File | Vai trò |
|------|---------|
| `tests/evaluation_suite.py` | Định nghĩa TEST_CASES + `evaluate_system()` |
| `scripts/run_evaluation.py` | Chạy đầy đủ 5 phương pháp + latency |
| `query/local_search.py` | Local Search |
| `query/global_search.py` | Global Search |
| `query/multihop_reasoning.py` | Multi-hop engine |
| `query/temporal_filter.py` | Lọc hiệu lực văn bản (E5) |
| `final_latex_report/DATN/Chuong/4_Ket_qua_thuc_nghiem.tex` | Chương báo cáo cần điền số |

---

*Tài liệu tạo để hỗ trợ thu số liệu thực nghiệm cho Chương 4 — Đồ án GraphRAG Luật Lao Động.*

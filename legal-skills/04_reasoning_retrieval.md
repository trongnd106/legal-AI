# SKILL 04 — Multi-hop Reasoning, Retrieval & Đánh giá

> Áp dụng cho: checklist mục 4.1 → 5.5
> Stack: GraphRAG Query API · Python · pandas · extensible rule engine

---

## Kiến trúc tổng quan

```
query/
├── __init__.py
├── loader.py              # Load GraphRagConfig + parquets (dùng chung)
├── global_search.py       # Global search — câu hỏi tổng quát
├── local_search.py        # Local search — câu hỏi cụ thể về Điều/Khoản
├── multihop_reasoning.py  # Multi-hop reasoning trên merged graph
├── temporal_filter.py     # Lọc hiệu lực văn bản
└── rule_validator.py      # Validation layer với quy tắc cứng

tests/
└── evaluation_suite.py    # Bộ test cases + hàm đánh giá
```

### Nguyên tắc quan trọng về dữ liệu

**Entity `type` trong parquet là UPPERCASE:**
GraphRAG chạy `.upper()` khi parse LLM output, nên:
- `ChuThe` → `CHUTHE`, `HanhVi` → `HANHVI`, `CheTai` → `CHETAI`, `XuLyKyLuat` → `XULYKYLUAT`
- Entity L1 (structural) giữ nguyên case: `Dieu`, `Khoan`, `VanBan`, `Chuong`, `CoQuan`

**Relationship `description` = tên relation type:**
Prompt của chúng ta dùng 6 field: `(relationship|source|target|rel_type|desc|weight)`.
GraphRAG map `field[3]` → `description`, nên `description = "entitles"`, `"obligates"`, v.v.
→ Lọc bằng `description.str.contains("obligates")` là chính xác.

**`context_data` từ API = `dict[str, pd.DataFrame]`**, không phải `{"sources": [...]}`.

---

## 1. Loader — Dùng chung cho mọi query module

```python
# query/loader.py — xem file đầy đủ trong source
from query.loader import GraphLoader

loader = GraphLoader("data/labor-law").load()
# loader.config             → GraphRagConfig
# loader.entities           → pd.DataFrame
# loader.communities        → pd.DataFrame
# loader.community_reports  → pd.DataFrame
# loader.text_units         → pd.DataFrame
# loader.relationships      → pd.DataFrame
# loader.covariates         → pd.DataFrame | None (optional)
# loader.artifacts_dir      → Path (tự tìm latest timestamp)

# Cho multi-hop reasoning: load merged graph
merged_ents, merged_rels = loader.load_merged_graph()
```

---

## 2. Global Search — Câu hỏi tổng quát

Phù hợp khi câu hỏi liên quan đến nhiều Điều hoặc cần tổng hợp toàn bộ chủ đề pháp lý.

```python
# query/global_search.py
import asyncio
from graphrag.api.query import global_search   # ← đúng import
from query.loader import GraphLoader

async def ask_global(
    question: str,
    loader: GraphLoader,
    domain_filter: str | None = None,     # "lao_dong" | "dan_su" | None
    community_level: int | None = 2,
    dynamic_community_selection: bool = False,
    response_type: str = "multiple paragraphs",
) -> dict:
    """
    Global search — tổng hợp toàn bộ hệ thống pháp luật VN.
    Trả về: {"answer", "domain_filter", "context_data", "article_citations"}
    """
    DOMAIN_LABELS = {
        "lao_dong":     "luật lao động, quan hệ lao động, hợp đồng lao động",
        "dan_su":       "luật dân sự, giao dịch dân sự, hợp đồng dân sự",
        ...
    }

    query = question
    if domain_filter:
        domain_ctx = DOMAIN_LABELS.get(domain_filter, "")
        if domain_ctx:
            query = f"[Lĩnh vực: {domain_ctx}] {question}"

    # API nhận GraphRagConfig + DataFrames, KHÔNG nhận file paths
    response, context_data = await global_search(
        config=loader.config,
        entities=loader.entities,
        communities=loader.communities,
        community_reports=loader.community_reports,
        community_level=community_level,
        dynamic_community_selection=dynamic_community_selection,
        response_type=response_type,
        query=query,
    )
    # context_data là dict[str, pd.DataFrame]
    return {
        "answer":            response,
        "domain_filter":     domain_filter,
        "context_data":      context_data,
        "article_citations": _extract_citations(str(response)),
    }
```

**Ví dụ chạy:**
```bash
python -m query.global_search data/labor-law \
    "Quyền cơ bản của người lao động là gì?" lao_dong
```

---

## 3. Local Search — Câu hỏi cụ thể về Điều/Khoản

```python
# query/local_search.py
from graphrag.api.query import local_search   # ← đúng import
from query.loader import GraphLoader

async def ask_local(
    question: str,
    loader: GraphLoader,
    community_level: int = 2,
    response_type: str = "single paragraph",
) -> dict:
    """
    Local search — tìm kiếm sâu về một Điều/Khoản cụ thể.
    Trả về: {"answer", "context_data", "article_citations", "entities_used"}
    """
    # API yêu cầu ĐẦY ĐỦ các DataFrames sau
    response, context_data = await local_search(
        config=loader.config,
        entities=loader.entities,
        communities=loader.communities,
        community_reports=loader.community_reports,
        text_units=loader.text_units,
        relationships=loader.relationships,
        covariates=loader.covariates,     # có thể là None
        community_level=community_level,
        response_type=response_type,
        query=question,
    )
    # context_data là dict[str, pd.DataFrame]
    # Trích citation từ câu trả lời (KHÔNG phải từ context_data["sources"])
    return {
        "answer":             response,
        "context_data":       context_data,
        "article_citations":  _extract_citations(str(response)),
        "entities_used":      _collect_entity_titles(context_data),
    }

def _collect_entity_titles(context_data: dict) -> list[str]:
    """context_data là dict[str, pd.DataFrame] — duyệt tất cả DataFrame có cột 'title'."""
    import pandas as pd
    titles = []
    if isinstance(context_data, dict):
        for value in context_data.values():
            if isinstance(value, pd.DataFrame) and "title" in value.columns:
                titles.extend(value["title"].dropna().tolist())
    return list(dict.fromkeys(titles))
```

**Ví dụ chạy:**
```bash
python -m query.local_search data/labor-law \
    "Người lao động được đơn phương chấm dứt HĐLĐ trong trường hợp nào?"
```

---

## 4. Multi-hop Reasoning Engine

Engine hoạt động trên **merged graph** (L1 structural + L2 LLM) từ `02_merge_structural_graph.py`.

```python
# query/multihop_reasoning.py
from query.loader import GraphLoader
from query.multihop_reasoning import VNLegalReasoningEngine

loader = GraphLoader("data/labor-law").load()
engine = VNLegalReasoningEngine(loader)

# Ví dụ 1: Vi phạm → chế tài
chain = engine.trace_chain(
    "không đóng bảo hiểm xã hội",
    chain_type="violation",
    domain="lao_dong",
)

# Ví dụ 2: Tự động phát hiện loại chain
chain_type = engine.detect_chain_type("NLĐ được hưởng nghỉ phép năm như thế nào?")
chain = engine.trace_chain("nghỉ phép năm", chain_type=chain_type)

print(chain.final_answer)
print("Căn cứ:", chain.cited_articles)
```

### Chain Templates (entity types đúng case)

| Template      | start_types               | hop_relations                              | end_types                   |
|---------------|--------------------------|--------------------------------------------|-----------------------------|
| `violation`   | `HANHVI`, `Dieu`         | `penalizes`, `disciplines`, `obligates`, `cites` | `CHETAI`, `XULYKYLUAT` |
| `entitlement` | `CHUTHE`, `Dieu`         | `entitles`, `requires_condition`, `applies_to`   | `NGHIPHEP`, `TIENLUONG`, `CHEDOBAOHIEM`, `TROCAPTHOIVIEC` |
| `procedure`   | `HANHVI`, `Dieu`, `HOPDONGLAODONG` | `applies_to`, `cites`, `enforced_by`, `guided_by` | `CoQuan` |

### Lọc quan hệ đúng cách

```python
# ĐÚNG — description chứa tên relation type (vì prompt format của chúng ta)
neighbors = self.relationships[
    (self.relationships["source"].str.upper() == entity_title.upper()) &
    self.relationships["description"].str.contains(
        "obligates|penalizes|entitles", case=False, na=False, regex=True
    )
]

# SAI — relationships không có cột "relation_type" riêng
# neighbors = self.relationships[self.relationships["relation_type"] == "obligates"]
```

### Tìm entities đúng cách

```python
# ĐÚNG — so sánh case-insensitive vì L1=camelCase, L2=UPPERCASE
mask = self.entities["type"].str.upper().isin(["HANHVI", "DIEU", "CHETAI"])

# SAI — type "HANH_VI" với underscore KHÔNG tồn tại
# mask = self.entities["type"].isin(["HANH_VI", "DIEU", "CHE_TAI"])
```

---

## 5. Temporal Filter — Lọc theo hiệu lực

```python
# query/temporal_filter.py
from query.temporal_filter import is_effective, filter_citations_by_effectiveness

# Kiểm tra văn bản đơn lẻ — dùng đúng so_hieu như trong metadata.json
print(is_effective("45/2019/QH14"))   # True
print(is_effective("12/2022/NĐ-CP"))  # True

# Lọc danh sách citations
result = filter_citations_by_effectiveness(
    ["Điều 35 BLLĐ 45/2019/QH14", "Điều 4 NĐ 12/2022"]
)
# {"valid_citations": [...], "expired_warnings": [...]}
```

**Cấu trúc `metadata.json` thực tế** (`data/labor-law/metadata.json`):
```json
{
  "45/2019/QH14": {
    "ten":           "Bộ luật Lao động 2019",
    "so_hieu":       "45/2019/QH14",
    "ngay_hieu_luc": "2021-01-01",
    "tinh_trang":    "con_hieu_luc",
    ...
  }
}
```
Key là `so_hieu`, cấu trúc là **dict** (không phải list như trong các ví dụ cũ).

---

## 6. Rule-based Validation Layer

```python
# query/rule_validator.py
from query.rule_validator import validate_answer

result = validate_answer(
    answer="Lương tối thiểu vùng I là 3.000.000 đồng/tháng",
    domain="lao_dong",
    question_keywords=["lương tối thiểu", "vùng I"],
)

if not result.is_valid:
    for w in result.warnings:
        print(w)
    # ⚠️ Mức lương 3.000.000 đồng thấp hơn lương tối thiểu vùng IV (3.450.000 đồng/tháng — NĐ 74/2024/NĐ-CP).
```

**Thêm domain mới:**
```python
DOMAIN_RULES["bat_dong_san"] = {
    "thoi_han_so_do":       50,   # năm đối với đất ở (Luật Đất đai 2024)
    "thue_chuyen_nhuong":    2,   # % giá trị chuyển nhượng
}
```

---

## 7. Pipeline tích hợp đầy đủ

```python
# scripts/04_query_pipeline.py
import asyncio
from query.loader import GraphLoader
from query.local_search import ask_local
from query.global_search import ask_global
from query.temporal_filter import filter_citations_by_effectiveness
from query.rule_validator import validate_answer
from query.multihop_reasoning import VNLegalReasoningEngine


async def answer_question(
    question: str,
    domain: str,
    loader: GraphLoader,
    engine: VNLegalReasoningEngine,
    use_global: bool = False,
) -> dict:
    """Pipeline đầy đủ: search → validate → temporal filter."""

    # Bước 1: Search
    if use_global:
        search_result = await ask_global(question, loader, domain_filter=domain)
    else:
        search_result = await ask_local(question, loader)

    answer   = str(search_result["answer"])
    citations = search_result.get("article_citations", [])

    # Bước 2: Multi-hop reasoning (bổ sung context)
    chain_type = engine.detect_chain_type(question)
    chain = engine.trace_chain(question, chain_type=chain_type, domain=domain)

    # Bước 3: Temporal filter
    temporal = filter_citations_by_effectiveness(citations)

    # Bước 4: Rule validation
    kw = question.lower().split()
    validation = validate_answer(answer, domain, question_keywords=kw)

    return {
        "answer":           answer,
        "cited_articles":   citations,
        "reasoning_chain":  chain.final_answer,
        "temporal_warnings": temporal["expired_warnings"],
        "validation":       validation,
    }


if __name__ == "__main__":
    loader = GraphLoader("data/labor-law").load()
    engine = VNLegalReasoningEngine(loader)

    test_questions = [
        ("Người lao động đơn phương chấm dứt HĐLĐ cần báo trước bao lâu?", "lao_dong"),
        ("Lương tối thiểu vùng I hiện tại là bao nhiêu?", "lao_dong"),
        ("Thời hiệu khởi kiện tranh chấp dân sự là bao nhiêu năm?", "dan_su"),
    ]

    for q, domain in test_questions:
        result = asyncio.run(answer_question(q, domain, loader, engine))
        print(f"\nQ: {q}")
        print(f"A: {result['answer'][:300]}")
        if result["temporal_warnings"]:
            print("TEMPORAL:", result["temporal_warnings"])
        if not result["validation"].is_valid:
            print("WARNINGS:", result["validation"].warnings)
```

---

## 8. Bộ test cases đa lĩnh vực

```python
# tests/evaluation_suite.py
import asyncio
from query.loader import GraphLoader
from query.local_search import ask_local
from tests.evaluation_suite import TEST_CASES, evaluate_system

loader = GraphLoader("data/labor-law").load()

def answer_fn(question: str, domain: str) -> dict:
    result = asyncio.run(ask_local(question, loader))
    return {
        "answer":        str(result["answer"]),
        "cited_articles": result["article_citations"],
    }

results = evaluate_system(answer_fn)
```

Bộ test bao gồm **25 test cases** thuộc 5 domain (`lao_dong`, `dan_su`, `hinh_su`,
`doanh_nghiep`, `cross_domain`) và 5 category
(`single_hop`, `multi_hop`, `temporal`, `cross_domain`), đủ để đo:
- Keyword Accuracy (target ≥ 70%)
- Citation Accuracy (target ≥ 60%)
- Cross-domain Accuracy (target ≥ 50%)

---

## Checklist hoàn thành mục này

- [ ] `ask_global()` với `domain_filter=None` trả lời được câu hỏi tổng quát liên lĩnh vực
- [ ] `ask_global()` với `domain_filter="lao_dong"` cho kết quả tốt hơn câu hỏi chỉ về lao động
- [ ] `ask_local()` trả về `article_citations` chứa số Điều cụ thể
- [ ] `VNLegalReasoningEngine.trace_chain()` chạy được với 3 `chain_type` khác nhau
- [ ] `validate_answer()` hoạt động đúng với ≥ 3 domain (`lao_dong`, `dan_su`, `hinh_su`)
- [ ] `filter_citations_by_effectiveness()` phát hiện được văn bản hết hiệu lực
- [ ] Bộ test cases có ≥ 25 cases, bao gồm ≥ 3 domain và ≥ 3 `cross_domain` cases
- [ ] Keyword Accuracy ≥ 70% tổng thể
- [ ] Citation Accuracy ≥ 60% tổng thể
- [ ] Cross-domain Accuracy ≥ 50%

---
name: rag-conflict-resolution
description: >
  Áp dụng skill này khi hệ thống RAG cần xử lý xung đột thông tin giữa các tài liệu.
  Trigger khi: (1) upload tài liệu mới có nội dung mâu thuẫn với tài liệu cũ,
  (2) truy vấn trả về nhiều chunk có thông tin trái chiều nhau, (3) cần thiết kế
  pipeline ingest tài liệu có khả năng phát hiện và giải quyết conflict.
  Áp dụng cho mọi domain: pháp lý, tài chính, y tế, quy định nội bộ.
---

# RAG Conflict Resolution — Hướng Dẫn Triển Khai

## Tổng quan

Khi hệ thống RAG nhận nhiều tài liệu, xung đột thông tin (conflict) là tất yếu — đặc biệt
với văn bản pháp quy, chính sách nội bộ, hoặc quy định được cập nhật theo thời gian.
Skill này định nghĩa một pipeline chuẩn gồm 4 tầng: **Metadata Extraction →
Conflict Detection → Resolution Strategy → Response Generation**.

Agent phải thực thi đúng thứ tự các tầng này, không được bỏ qua bước nào.

---

## Tầng 1 — Metadata Extraction (Khi Ingest Tài Liệu)

Mỗi tài liệu upload vào hệ thống **bắt buộc** phải được gắn metadata trước khi index.
Nếu metadata không có sẵn trong tài liệu, agent phải suy luận từ nội dung hoặc yêu cầu
người dùng cung cấp.

### Schema metadata chuẩn

```python
document_metadata = {
    # --- Định danh ---
    "doc_id": "str",              # UUID duy nhất, tự sinh
    "doc_name": "str",            # Tên file gốc
    "doc_hash": "str",            # SHA-256 của nội dung — dùng để phát hiện duplicate

    # --- Thời gian & hiệu lực ---
    "issued_date": "YYYY-MM-DD",  # Ngày ban hành (quan trọng nhất để so sánh)
    "effective_date": "YYYY-MM-DD", # Ngày có hiệu lực (nếu khác issued_date)
    "expiry_date": "YYYY-MM-DD | null", # Ngày hết hiệu lực (nếu có)

    # --- Nguồn & thẩm quyền ---
    "source_type": "official | internal | external | draft",
    "issuing_authority": "str",   # Ví dụ: "Chính phủ", "Bộ Tài chính", "Ban Giám đốc"
    "authority_level": "int",     # 1 = cao nhất (luật), 5 = thấp nhất (hướng dẫn nội bộ)

    # --- Phiên bản ---
    "version": "str",             # "v1.0", "v2.3", ...
    "supersedes": ["doc_id_1"],   # Danh sách doc_id bị thay thế bởi tài liệu này
    "priority_score": "float",    # Tính tự động (xem công thức bên dưới)

    # --- Trạng thái ---
    "status": "active | deprecated | draft | conflict_flagged"
}
```

### Công thức tính priority_score

```python
from datetime import datetime

def compute_priority_score(meta: dict) -> float:
    """
    Score càng cao = tài liệu càng được ưu tiên khi conflict.
    Thang điểm: 0.0 – 1.0
    """
    now = datetime.now()

    # 1. Điểm thẩm quyền (40%) — authority_level 1 là cao nhất
    authority_score = (6 - meta["authority_level"]) / 5  # level 1 → 1.0, level 5 → 0.2

    # 2. Điểm thời gian (40%) — tài liệu càng mới càng cao điểm
    issued = datetime.strptime(meta["issued_date"], "%Y-%m-%d")
    days_old = (now - issued).days
    recency_score = max(0, 1 - (days_old / 3650))  # Decay tuyến tính trong 10 năm

    # 3. Điểm source_type (20%)
    source_weight = {
        "official": 1.0,
        "internal": 0.7,
        "external": 0.5,
        "draft":    0.2
    }
    source_score = source_weight.get(meta["source_type"], 0.5)

    return round(
        0.4 * authority_score +
        0.4 * recency_score +
        0.2 * source_score,
        4
    )
```

---

## Tầng 2 — Conflict Detection (Khi Retrieval)

Sau khi retrieval trả về danh sách chunks, agent **phải chạy bước phát hiện conflict**
trước khi đưa vào LLM. Không được bỏ qua bước này.

### Điều kiện xác định conflict

Hai chunks được coi là conflict nếu thoả mãn **đồng thời** hai điều kiện:

1. **Semantic overlap cao** — cùng nói về một thực thể/chủ đề (cosine similarity > 0.75)
2. **Factual divergence** — giá trị cụ thể khác nhau (số tiền, ngày, tỉ lệ, tên...)

```python
def detect_conflicts(chunks: list[dict]) -> list[dict]:
    """
    Input: danh sách chunks đã retrieve, mỗi chunk có 'text' và 'metadata'
    Output: danh sách các cặp conflict được phát hiện
    """
    conflicts = []

    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            chunk_a = chunks[i]
            chunk_b = chunks[j]

            # Bỏ qua nếu cùng một tài liệu
            if chunk_a["metadata"]["doc_id"] == chunk_b["metadata"]["doc_id"]:
                continue

            # Kiểm tra semantic overlap
            sim = cosine_similarity(
                embed(chunk_a["text"]),
                embed(chunk_b["text"])
            )
            if sim < 0.75:
                continue

            # Kiểm tra factual divergence bằng LLM mini-call
            verdict = llm_check_factual_conflict(chunk_a["text"], chunk_b["text"])
            # verdict: {"is_conflict": bool, "conflict_description": str, "conflicting_values": dict}

            if verdict["is_conflict"]:
                conflicts.append({
                    "chunk_a": chunk_a,
                    "chunk_b": chunk_b,
                    "conflict_description": verdict["conflict_description"],
                    "conflicting_values": verdict["conflicting_values"],
                    "severity": classify_severity(verdict["conflicting_values"])
                })

    return conflicts


def classify_severity(conflicting_values: dict) -> str:
    """
    critical  — mâu thuẫn về con số tài chính, mức phạt, điều khoản pháp lý
    high      — mâu thuẫn về thời hạn, ngày tháng, quy trình bắt buộc
    medium    — mâu thuẫn về định nghĩa, phân loại, danh mục
    low       — mâu thuẫn thông tin nền, không ảnh hưởng quyết định
    """
    # Agent tự implement logic phù hợp với domain
    ...
```

### Prompt gọi LLM để kiểm tra conflict

```
SYSTEM:
Bạn là chuyên gia phát hiện mâu thuẫn thông tin. Nhiệm vụ: so sánh hai đoạn văn bản
và xác định xem chúng có chứa thông tin factual mâu thuẫn nhau không.
Chỉ quan tâm đến mâu thuẫn về dữ liệu cụ thể (số tiền, ngày, tỉ lệ, tên, điều kiện).
Bỏ qua sự khác biệt về cách diễn đạt.
Trả về JSON với schema: {"is_conflict": bool, "conflict_description": str, "conflicting_values": {"field": {"a": val, "b": val}}}

USER:
Đoạn A: {chunk_a_text}
Đoạn B: {chunk_b_text}
```

---

## Tầng 3 — Resolution Strategy (Chiến lược Giải quyết)

Khi phát hiện conflict, agent áp dụng chiến lược theo thứ tự ưu tiên sau.
**Dừng lại ở chiến lược đầu tiên áp dụng được**, không áp dụng nhiều chiến lược cùng lúc.

```
┌─────────────────────────────────────────────────────┐
│              CONFLICT RESOLUTION FLOWCHART           │
└─────────────────────────────────────────────────────┘

[Conflict detected]
        │
        ▼
┌───────────────────┐   YES  ┌──────────────────────────────┐
│ doc_A.supersedes  │───────▶│ STRATEGY 1: Auto-deprecate   │
│ chứa doc_B.doc_id?│        │ Dùng doc_A, đánh dấu doc_B  │
│ (hoặc ngược lại)  │        │ status = "deprecated"        │
└───────────────────┘        └──────────────────────────────┘
        │ NO
        ▼
┌───────────────────┐   YES  ┌──────────────────────────────┐
│ authority_level   │───────▶│ STRATEGY 2: Authority-based  │
│ khác nhau?        │        │ Dùng doc có authority_level  │
│                   │        │ thấp hơn (= cấp cao hơn)     │
└───────────────────┘        └──────────────────────────────┘
        │ NO
        ▼
┌───────────────────┐   YES  ┌──────────────────────────────┐
│ priority_score    │───────▶│ STRATEGY 3: Score-based      │
│ chênh lệch        │        │ Dùng doc có priority_score   │
│ > 0.15?           │        │ cao hơn                      │
└───────────────────┘        └──────────────────────────────┘
        │ NO
        ▼
┌───────────────────────────────────────────────────────┐
│ STRATEGY 4: Transparent Multi-source                  │
│ Trình bày cả hai nguồn, nêu rõ mâu thuẫn,            │
│ đề xuất người dùng xác nhận nguồn chính thức         │
└───────────────────────────────────────────────────────┘
```

### Triển khai chiến lược

```python
def resolve_conflict(conflict: dict) -> dict:
    chunk_a = conflict["chunk_a"]
    chunk_b = conflict["chunk_b"]
    meta_a  = chunk_a["metadata"]
    meta_b  = chunk_b["metadata"]

    # --- Strategy 1: Explicit supersession ---
    if meta_b["doc_id"] in meta_a.get("supersedes", []):
        return {
            "strategy": "auto_deprecate",
            "winner": chunk_a,
            "loser":  chunk_b,
            "reason": f"{meta_a['doc_name']} thay thế {meta_b['doc_name']}",
            "action": "deprecate_loser"
        }
    if meta_a["doc_id"] in meta_b.get("supersedes", []):
        return {
            "strategy": "auto_deprecate",
            "winner": chunk_b,
            "loser":  chunk_a,
            "reason": f"{meta_b['doc_name']} thay thế {meta_a['doc_name']}",
            "action": "deprecate_loser"
        }

    # --- Strategy 2: Authority level ---
    if meta_a["authority_level"] != meta_b["authority_level"]:
        winner = chunk_a if meta_a["authority_level"] < meta_b["authority_level"] else chunk_b
        loser  = chunk_b if winner == chunk_a else chunk_a
        return {
            "strategy": "authority_based",
            "winner": winner,
            "loser":  loser,
            "reason": f"Ưu tiên theo thẩm quyền: level {winner['metadata']['authority_level']}",
            "action": "flag_loser"  # không xoá, chỉ gắn cờ
        }

    # --- Strategy 3: Priority score ---
    score_a = meta_a["priority_score"]
    score_b = meta_b["priority_score"]
    if abs(score_a - score_b) > 0.15:
        winner = chunk_a if score_a > score_b else chunk_b
        loser  = chunk_b if winner == chunk_a else chunk_a
        return {
            "strategy": "score_based",
            "winner": winner,
            "loser":  loser,
            "reason": f"Priority score: {max(score_a, score_b):.3f} > {min(score_a, score_b):.3f}",
            "action": "flag_loser"
        }

    # --- Strategy 4: Transparent multi-source ---
    return {
        "strategy": "multi_source",
        "sources":  [chunk_a, chunk_b],
        "reason":   "Không đủ cơ sở tự động xác định nguồn đáng tin hơn",
        "action":   "present_both_flag_admin"
    }
```

---

## Tầng 4 — Response Generation (Tạo Câu Trả Lời)

Agent sử dụng kết quả từ Tầng 3 để tạo prompt cho LLM cuối cùng.

### Trường hợp đã resolve được (Strategy 1, 2, 3)

```
SYSTEM:
Trả lời dựa trên tài liệu được cung cấp. Hệ thống đã phát hiện mâu thuẫn giữa
các nguồn và đã xác định nguồn ưu tiên theo quy tắc: {resolution.reason}.
Chỉ sử dụng thông tin từ nguồn được ưu tiên. Cuối câu trả lời, ghi chú ngắn
về việc có tài liệu khác và lý do tài liệu nào được ưu tiên.

NGUỒN ƯU TIÊN:
Tài liệu: {winner.metadata.doc_name}
Ban hành: {winner.metadata.issued_date}
Thẩm quyền: {winner.metadata.issuing_authority}
Nội dung: {winner.text}

CÂU HỎI: {user_query}

YÊU CẦU OUTPUT:
1. Câu trả lời chính xác từ nguồn ưu tiên
2. Dòng ghi chú: "⚠️ Lưu ý: Có tài liệu [{loser.doc_name}] nêu khác ({conflicting_value}).
   Hệ thống ưu tiên [{winner.doc_name}] vì {resolution.reason}."
```

### Trường hợp không resolve được (Strategy 4)

```
SYSTEM:
Hệ thống phát hiện mâu thuẫn thông tin giữa các nguồn và không thể tự động xác định
nguồn nào chính xác hơn. Trình bày trung thực cả hai quan điểm, nêu rõ sự khác biệt,
và khuyến nghị người dùng xác nhận với bộ phận có thẩm quyền.

NGUỒN A:
Tài liệu: {chunk_a.metadata.doc_name} | Ngày: {chunk_a.metadata.issued_date}
Nội dung: {chunk_a.text}

NGUỒN B:
Tài liệu: {chunk_b.metadata.doc_name} | Ngày: {chunk_b.metadata.issued_date}
Nội dung: {chunk_b.text}

MÂU THUẪN: {conflict.conflict_description}

CÂU HỎI: {user_query}

YÊU CẦU OUTPUT:
1. Nêu rõ có mâu thuẫn giữa các nguồn
2. Trình bày từng quan điểm với trích dẫn nguồn
3. KHÔNG tự bịa ra câu trả lời cuối cùng
4. Khuyến nghị: "Vui lòng xác nhận với [bộ phận/cơ quan có thẩm quyền]"
```

---

## Pipeline Hoàn Chỉnh

```python
class RAGConflictResolutionPipeline:
    """
    Pipeline đầy đủ: từ query đến response có xử lý conflict.
    """

    def run(self, user_query: str) -> dict:

        # Bước 1: Retrieve chunks thông thường
        raw_chunks = self.retriever.retrieve(user_query, top_k=10)

        # Bước 2: Lọc chunks theo status (không dùng deprecated)
        active_chunks = [
            c for c in raw_chunks
            if c["metadata"]["status"] in ("active", "conflict_flagged")
        ]

        # Bước 3: Detect conflict
        conflicts = detect_conflicts(active_chunks)

        # Bước 4: Resolve từng conflict
        resolutions = [resolve_conflict(c) for c in conflicts]

        # Bước 5: Xác định winning chunks để đưa vào LLM
        winning_chunks = self._select_winning_chunks(active_chunks, resolutions)

        # Bước 6: Ghi log conflict để admin review
        if conflicts:
            self.conflict_log.write(user_query, conflicts, resolutions)

        # Bước 7: Tạo response
        if any(r["strategy"] == "multi_source" for r in resolutions):
            response = self._generate_ambiguous_response(
                user_query, winning_chunks, resolutions
            )
        else:
            response = self._generate_resolved_response(
                user_query, winning_chunks, resolutions
            )

        return {
            "answer": response,
            "conflicts_detected": len(conflicts),
            "resolutions": resolutions,
            "sources_used": [c["metadata"]["doc_name"] for c in winning_chunks]
        }

    def _select_winning_chunks(self, chunks, resolutions):
        """Loại bỏ losing chunks khỏi context (trừ multi_source giữ cả hai)."""
        loser_ids = set()
        for r in resolutions:
            if r["strategy"] in ("auto_deprecate", "authority_based", "score_based"):
                loser_ids.add(r["loser"]["metadata"]["doc_id"])
        return [c for c in chunks if c["metadata"]["doc_id"] not in loser_ids]
```

---

## Hành vi Bắt Buộc Của Agent

Agent **PHẢI** tuân thủ các quy tắc sau, không có ngoại lệ:

| # | Quy tắc | Lý do |
|---|---------|-------|
| 1 | Không bao giờ trả lời từ chunk có `status = "deprecated"` | Thông tin đã lỗi thời |
| 2 | Luôn cite nguồn (doc_name + issued_date) trong mọi câu trả lời | Truy xuất nguồn gốc |
| 3 | Khi dùng Strategy 4, **không tự chọn** một trong hai nguồn | Tránh hallucination |
| 4 | Khi severity = "critical", **luôn dùng Strategy 4** dù score chênh lệch | An toàn tuyệt đối |
| 5 | Ghi log mọi conflict được phát hiện, kể cả đã resolve được | Audit trail |
| 6 | Thông báo admin khi có conflict `severity = critical` hoặc `high` | Cần review thủ công |

---

## Ví dụ Minh Hoạ

### Kịch bản: Hai văn bản quy định mức phạt khác nhau

**Input:**
- Tài liệu A (Nghị định 01/2023, authority_level=2): "Lỗi X phạt 2.000.000đ"
- Tài liệu B (Thông tư 05/2024, authority_level=3): "Lỗi X phạt 2.500.000đ"
- Query: "Lỗi X bị phạt bao nhiêu?"

**Xử lý:**
```
1. Detect conflict → is_conflict: true, severity: "critical"
2. Strategy 1: không có supersedes → skip
3. Strategy 2: authority_level khác nhau (2 vs 3) → APPLY
   → winner: Tài liệu A (Nghị định, authority_level=2)
   → loser:  Tài liệu B (Thông tư, authority_level=3)
```

**Output:**
```
Theo Nghị định 01/2023 (ban hành ngày 15/01/2023), lỗi X bị phạt 2.000.000đ.

⚠️ Lưu ý: Thông tư 05/2024 nêu mức phạt là 2.500.000đ. Hệ thống ưu tiên
Nghị định 01/2023 vì có thẩm quyền pháp lý cao hơn (Nghị định > Thông tư).
Nếu Thông tư 05/2024 là văn bản hướng dẫn thi hành Nghị định mới hơn,
vui lòng xác nhận lại với bộ phận pháp chế.
```

---

## Lưu ý Khi Triển Khai

- **Embedding model** dùng để tính cosine similarity phải là model đa ngôn ngữ
  (ví dụ: `multilingual-e5-large`, `bge-m3`) nếu tài liệu tiếng Việt.
- **Ngưỡng 0.75** cho cosine similarity có thể cần điều chỉnh theo domain —
  văn bản pháp lý thường cần ngưỡng cao hơn (0.80–0.85).
- **authority_level** phải được định nghĩa rõ ràng theo từng tổ chức trước khi triển khai.
  Ví dụ gợi ý: `1=Luật/Bộ luật, 2=Nghị định, 3=Thông tư, 4=Quyết định nội bộ, 5=Hướng dẫn`.
- **Conflict log** nên được review định kỳ (hàng tuần) để phát hiện pattern tài liệu
  cần được cập nhật hoặc deprecated thủ công.

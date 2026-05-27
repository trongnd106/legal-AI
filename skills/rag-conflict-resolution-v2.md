---
name: rag-conflict-resolution-v2
description: >
  Phiên bản 2 — Xử lý xung đột tại thời điểm INDEXING (ingest-time), thay vì
  chỉ xử lý khi answer (query-time) như v1.
  Trigger khi: (1) upload / index tài liệu mới vào hệ thống, (2) cần thiết kế
  lại pipeline `index_per_file.py` hoặc workflow GraphRAG để phát hiện conflict
  sớm và gắn metadata trạng thái vào parquet/Neo4j ngay lúc ingest.
  Áp dụng cho domain pháp lý Việt Nam (Luật, Nghị định, Thông tư, Quyết định).
---

# RAG Conflict Resolution v2 — Xử Lý Conflict Tại Thời Điểm Index

## So sánh v1 vs v2

| Tiêu chí | v1 (query-time) | v2 (index-time) |
|---|---|---|
| **Khi nào phát hiện conflict** | Mỗi lần query, sau retrieval | Một lần duy nhất khi ingest |
| **Chi phí LLM** | Gọi LLM mỗi query | Gọi LLM một lần khi ingest |
| **Latency câu trả lời** | Tăng (phải detect + resolve mỗi query) | Không tăng (conflict đã biết trước) |
| **Độ phủ** | Chỉ phát hiện conflict trong top-K retrieved | Phát hiện toàn bộ corpus |
| **Dữ liệu cũ (parquet/Neo4j)** | Không thay đổi | Cần migration một lần (xem §5) |
| **Độ phức tạp triển khai** | Thấp | Trung bình |

---

## Tổng quan kiến trúc v2

```
┌──────────────────────────────────────────────────────────────────┐
│                    INDEX-TIME PIPELINE (v2)                       │
└──────────────────────────────────────────────────────────────────┘

  [File mới upload]
        │
        ▼
  ┌─────────────┐
  │ Tầng 1      │  Metadata Extraction
  │ (giữ nguyên │  (đọc doc_name, issued_date, authority_level...)
  │  từ v1)     │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Tầng 1b     │  [MỚI] Duplicate Check
  │ (NEW)       │  SHA-256 hash → nếu đã tồn tại → skip
  └──────┬──────┘
         │ chưa tồn tại
         ▼
  ┌─────────────┐
  │ Tầng 2      │  GraphRAG Standard Index
  │ (GraphRAG)  │  (chunk → embed → extract_graph → community)
  └──────┬──────┘
         │ parquet output
         ▼
  ┌─────────────────────┐
  │ Tầng 3 (NEW)        │  Index-time Conflict Scan
  │ conflict_scanner.py │  So sánh doc mới với TẤT CẢ doc hiện có
  └──────┬──────────────┘
         │
         ▼
  ┌─────────────────────┐
  │ Tầng 4 (NEW)        │  Conflict Resolution & Metadata Update
  │ conflict_resolver.py│  Áp dụng Strategy 1-4, ghi conflict_registry
  └──────┬──────────────┘
         │
         ▼
  ┌─────────────────────┐
  │ Tầng 5              │  Neo4j MERGE
  │ (mở rộng từ v1)     │  + ghi thêm ConflictEdge, cập nhật status node
  └─────────────────────┘

  [Query-time: chỉ lọc status + lookup conflict_registry, KHÔNG detect lại]
```

---

## Tầng 1 — Metadata Extraction (giữ nguyên từ v1)

Schema metadata không đổi so với v1. Thêm một trường mới:

```python
document_metadata = {
    # --- (giữ nguyên toàn bộ v1) ---
    "doc_id":           "str",
    "doc_name":         "str",
    "doc_hash":         "str",           # SHA-256
    "issued_date":      "YYYY-MM-DD",
    "effective_date":   "YYYY-MM-DD",
    "expiry_date":      "YYYY-MM-DD | null",
    "source_type":      "official | internal | external | draft",
    "issuing_authority":"str",
    "authority_level":  "int",           # 1=Luật, 2=Nghị định, 3=Thông tư, 4=QĐ, 5=Hướng dẫn
    "version":          "str",
    "supersedes":       ["doc_id_1"],
    "priority_score":   "float",
    "status":           "active | deprecated | draft | conflict_flagged",

    # --- THÊM MỚI cho v2 ---
    "known_conflicts":  ["doc_id_X", "doc_id_Y"],  # điền sau khi chạy conflict scan
    "conflict_resolved_by": "str | null",           # strategy áp dụng: auto_deprecate / authority_based / score_based / manual
    "indexed_at":       "ISO-8601 timestamp",       # khi nào file này được index
}
```

---

## Tầng 1b — Duplicate Check (MỚI)

Trước khi gọi GraphRAG index tốn kém, kiểm tra hash để tránh index lại:

```python
import hashlib
from pathlib import Path

def compute_file_hash(file_path: Path) -> str:
    """SHA-256 của nội dung file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_duplicate(doc_hash: str, registry: dict) -> bool:
    """Kiểm tra hash trong document registry (parquet hoặc DB)."""
    return doc_hash in registry.get("hashes", set())
```

---

## Tầng 3 — Index-time Conflict Scan (MỚI, QUAN TRỌNG NHẤT)

Chạy **ngay sau** khi GraphRAG index xong file mới (parquet đã có), trước khi MERGE vào Neo4j.

### Thuật toán

```python
import pandas as pd
from pathlib import Path

def run_conflict_scan_after_index(
    new_doc_meta: dict,
    new_doc_chunks: list[dict],      # chunks vừa được index của doc mới
    existing_corpus_chunks: list[dict],  # toàn bộ chunks trong corpus hiện tại
    conflict_registry_path: Path,    # file JSON lưu lịch sử conflict
) -> list[dict]:
    """
    So sánh doc mới với toàn bộ corpus để tìm conflict.

    Tối ưu: chỉ so sánh chunk của doc mới với chunks từ doc KHÁC,
    không cần so sánh tất cả với tất cả (O(n^2) sẽ quá chậm).
    """
    conflicts_found = []

    # Nhóm chunk theo doc_id để tra cứu nhanh
    existing_by_doc: dict[str, list] = {}
    for c in existing_corpus_chunks:
        did = c["metadata"]["doc_id"]
        existing_by_doc.setdefault(did, []).append(c)

    new_doc_id = new_doc_meta["doc_id"]

    # Chỉ xét doc trong corpus có thể liên quan (cùng authority domain)
    candidate_docs = _filter_candidate_docs(
        new_doc_meta, existing_by_doc
    )

    for target_doc_id, target_chunks in candidate_docs.items():
        # Tìm cặp chunk có semantic overlap cao nhất (đại diện cho 2 doc)
        best_pairs = _find_representative_pairs(
            new_doc_chunks, target_chunks, top_n=3
        )

        for pair in best_pairs:
            chunk_a, chunk_b, sim = pair
            if sim < 0.75:
                continue

            verdict = llm_check_factual_conflict(
                chunk_a["text"], chunk_b["text"]
            )

            if verdict["is_conflict"]:
                conflict = {
                    "conflict_id": f"conflict_{new_doc_id[:8]}_{target_doc_id[:8]}",
                    "detected_at": "index_time",
                    "doc_new": new_doc_id,
                    "doc_existing": target_doc_id,
                    "chunk_new": chunk_a,
                    "chunk_existing": chunk_b,
                    "semantic_similarity": sim,
                    "conflict_description": verdict["conflict_description"],
                    "conflicting_values": verdict["conflicting_values"],
                    "severity": classify_severity(verdict["conflicting_values"]),
                }
                conflicts_found.append(conflict)

    # Ghi vào conflict registry
    _append_to_conflict_registry(conflicts_found, conflict_registry_path)

    return conflicts_found


def _filter_candidate_docs(
    new_doc_meta: dict,
    existing_by_doc: dict
) -> dict:
    """
    Lọc sơ bộ các doc có khả năng conflict để tránh so sánh toàn bộ.

    Ưu tiên so sánh:
    - Doc cùng authority_level ± 2
    - Doc có issued_date trong vòng 10 năm
    - Doc chưa bị deprecated
    """
    candidates = {}
    new_date = new_doc_meta.get("issued_date", "2000-01-01")
    new_level = new_doc_meta.get("authority_level", 3)

    for doc_id, chunks in existing_by_doc.items():
        if not chunks:
            continue
        meta = chunks[0]["metadata"]

        # Bỏ qua doc đã deprecated
        if meta.get("status") == "deprecated":
            continue

        # Bỏ qua doc quá khác cấp độ thẩm quyền (ví dụ Luật vs Hướng dẫn nội bộ)
        if abs(meta.get("authority_level", 3) - new_level) > 2:
            continue

        candidates[doc_id] = chunks

    return candidates


def _find_representative_pairs(
    chunks_a: list, chunks_b: list, top_n: int = 3
) -> list[tuple]:
    """
    Tìm top_n cặp (chunk_a, chunk_b) có cosine similarity cao nhất.
    Trả về list of (chunk_a, chunk_b, similarity).
    """
    pairs = []
    for ca in chunks_a:
        for cb in chunks_b:
            sim = cosine_similarity(embed(ca["text"]), embed(cb["text"]))
            pairs.append((ca, cb, sim))

    # Sắp xếp giảm dần và lấy top_n
    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs[:top_n]
```

### Tối ưu chi phí embedding

```python
# Thay vì embed từng chunk riêng lẻ, batch toàn bộ trong một lần gọi
def batch_embed_chunks(chunks: list[dict], embed_fn) -> list[dict]:
    texts = [c["text"] for c in chunks]
    vectors = embed_fn(texts)  # batch call
    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec
    return chunks
```

---

## Tầng 4 — Conflict Resolution tại Index-time (MỚI)

Áp dụng cùng 4 strategy từ v1, nhưng kết quả được lưu vào **conflict_registry** và **cập nhật metadata** — không phải xử lý lại mỗi query.

```python
def resolve_and_persist_conflicts(
    conflicts: list[dict],
    doc_registry: dict,       # {doc_id: metadata} — toàn bộ corpus
    conflict_registry_path: Path,
) -> list[dict]:
    """
    Resolve conflict tại index-time và cập nhật metadata tài liệu.
    """
    resolutions = []

    for conflict in conflicts:
        meta_new = doc_registry[conflict["doc_new"]]
        meta_existing = doc_registry[conflict["doc_existing"]]

        resolution = _apply_resolution_strategy(meta_new, meta_existing, conflict)
        resolutions.append(resolution)

        # Cập nhật metadata ngay — sẽ được persist vào parquet/Neo4j
        _update_doc_metadata_post_resolution(
            resolution, doc_registry
        )

    return resolutions


def _apply_resolution_strategy(
    meta_a: dict, meta_b: dict, conflict: dict
) -> dict:
    """Áp dụng 4 strategy theo đúng thứ tự ưu tiên (giữ nguyên logic v1)."""

    # Strategy 1: Explicit supersedes
    if meta_b["doc_id"] in meta_a.get("supersedes", []):
        return {"strategy": "auto_deprecate", "winner": meta_a["doc_id"],
                "loser": meta_b["doc_id"], "action": "deprecate_loser",
                "reason": f"{meta_a['doc_name']} thay thế {meta_b['doc_name']}"}

    if meta_a["doc_id"] in meta_b.get("supersedes", []):
        return {"strategy": "auto_deprecate", "winner": meta_b["doc_id"],
                "loser": meta_a["doc_id"], "action": "deprecate_loser",
                "reason": f"{meta_b['doc_name']} thay thế {meta_a['doc_name']}"}

    # Strategy 2: Authority level
    if meta_a["authority_level"] != meta_b["authority_level"]:
        winner = meta_a if meta_a["authority_level"] < meta_b["authority_level"] else meta_b
        loser  = meta_b if winner == meta_a else meta_a
        return {"strategy": "authority_based", "winner": winner["doc_id"],
                "loser": loser["doc_id"], "action": "flag_loser",
                "reason": f"Thẩm quyền: level {winner['authority_level']} > level {loser['authority_level']}"}

    # Strategy 3: Priority score
    sa, sb = meta_a["priority_score"], meta_b["priority_score"]
    if abs(sa - sb) > 0.15:
        winner = meta_a if sa > sb else meta_b
        loser  = meta_b if winner == meta_a else meta_a
        return {"strategy": "score_based", "winner": winner["doc_id"],
                "loser": loser["doc_id"], "action": "flag_loser",
                "reason": f"Priority score: {max(sa,sb):.3f} vs {min(sa,sb):.3f}"}

    # Strategy 4: Ambiguous — cần admin review
    return {
        "strategy": "needs_review",
        "winner": None,
        "loser": None,
        "action": "flag_both_notify_admin",
        "reason": "Không đủ cơ sở tự động phân giải — cần xác nhận thủ công",
        "conflict_id": conflict["conflict_id"],
    }


def _update_doc_metadata_post_resolution(
    resolution: dict, doc_registry: dict
) -> None:
    """Cập nhật status và conflict metadata vào registry (sẽ persist)."""
    if resolution["strategy"] == "auto_deprecate":
        doc_registry[resolution["loser"]]["status"] = "deprecated"

    elif resolution["strategy"] in ("authority_based", "score_based"):
        doc_registry[resolution["loser"]]["status"] = "conflict_flagged"
        # Ghi nhận conflict để query-time biết
        loser_meta = doc_registry[resolution["loser"]]
        loser_meta.setdefault("known_conflicts", []).append(resolution["winner"])

    elif resolution["strategy"] == "needs_review":
        # Gắn cờ cả hai
        for doc_id in (resolution.get("doc_new"), resolution.get("doc_existing")):
            if doc_id and doc_id in doc_registry:
                doc_registry[doc_id]["status"] = "conflict_flagged"
```

---

## Tầng 5 — Neo4j MERGE mở rộng (MỚI: ConflictEdge)

Sau khi resolve conflict, ghi thêm quan hệ `CONFLICTS_WITH` vào Neo4j:

```cypher
-- Tạo constraint (chạy một lần)
CREATE CONSTRAINT conflict_id IF NOT EXISTS
  FOR ()-[r:CONFLICTS_WITH]-()
  REQUIRE r.conflict_id IS NOT NULL;

-- MERGE conflict relationship (gọi từ Python sau mỗi conflict resolved)
MERGE (a:Document {id: $doc_id_a})
MERGE (b:Document {id: $doc_id_b})
MERGE (a)-[r:CONFLICTS_WITH {conflict_id: $conflict_id}]-(b)
SET r.severity          = $severity,
    r.strategy          = $strategy,
    r.winner_doc_id     = $winner,
    r.conflict_desc     = $description,
    r.detected_at       = $detected_at,
    r.resolved          = $resolved
```

```python
def neo4j_merge_conflict(driver, conflict: dict, resolution: dict) -> None:
    """Ghi conflict edge vào Neo4j."""
    with driver.session() as s:
        s.run("""
            MERGE (a:Document {id: $doc_a})
            MERGE (b:Document {id: $doc_b})
            MERGE (a)-[r:CONFLICTS_WITH {conflict_id: $cid}]-(b)
            SET r.severity    = $severity,
                r.strategy    = $strategy,
                r.winner      = $winner,
                r.description = $desc,
                r.detected_at = $ts,
                r.resolved    = $resolved
        """, {
            "doc_a":    conflict["doc_new"],
            "doc_b":    conflict["doc_existing"],
            "cid":      conflict["conflict_id"],
            "severity": conflict["severity"],
            "strategy": resolution["strategy"],
            "winner":   resolution.get("winner"),
            "desc":     conflict["conflict_description"],
            "ts":       conflict["detected_at"],
            "resolved": resolution["strategy"] != "needs_review",
        })

    # Cập nhật status node nếu cần
    if resolution["strategy"] == "auto_deprecate":
        with driver.session() as s:
            s.run(
                "MATCH (d:Document {id: $id}) SET d.status = 'deprecated'",
                {"id": resolution["loser"]}
            )
```

---

## Tích hợp vào `index_per_file.py`

Thêm bước conflict scan ngay sau khi GraphRAG index thành công, trước Neo4j sync:

```python
# Trong hàm main(), sau `exit_code = run_command(...)`:

if exit_code == 0:
    # [MỚI - v2] Chạy conflict scan trước khi sync Neo4j
    new_doc_meta = load_metadata_for_file(source_file)   # đọc từ parquet mới
    new_chunks   = load_chunks_from_output(output_dir)   # đọc text_units.parquet
    corpus_chunks = load_all_corpus_chunks(corpus_db)    # đọc từ registry/parquet cũ

    conflicts  = run_conflict_scan_after_index(
        new_doc_meta, new_chunks, corpus_chunks, conflict_registry_path
    )
    resolutions = resolve_and_persist_conflicts(
        conflicts, doc_registry, conflict_registry_path
    )

    if any(r["strategy"] == "needs_review" for r in resolutions):
        notify_admin(conflicts, resolutions)  # email/Slack alert

    # Sync Neo4j (bây giờ có thêm ConflictEdge)
    if use_neo4j and neo4j_driver:
        neo4j_sync_after_run(neo4j_driver, workspace_root, source_file.name)
        for c, r in zip(conflicts, resolutions):
            neo4j_merge_conflict(neo4j_driver, c, r)
```

---

## Query-time Pipeline (đơn giản hóa so với v1)

Vì conflict đã được phát hiện và giải quyết tại index-time, query-time chỉ cần:

```python
class RAGConflictResolutionPipeline_v2:

    def run(self, user_query: str) -> dict:

        # Bước 1: Retrieve — chỉ lấy chunk không bị deprecated
        raw_chunks = self.retriever.retrieve(user_query, top_k=10)
        active_chunks = [
            c for c in raw_chunks
            if c["metadata"]["status"] != "deprecated"
        ]

        # Bước 2: Lookup conflict registry (đọc từ file/cache, KHÔNG gọi LLM)
        known_conflicts = self.conflict_registry.get_conflicts_for_chunks(active_chunks)

        # Bước 3: Chỉ cần tạo response — không phải detect conflict nữa
        if known_conflicts:
            response = self._generate_response_with_known_conflicts(
                user_query, active_chunks, known_conflicts
            )
        else:
            response = self._generate_normal_response(user_query, active_chunks)

        return {"answer": response, "conflicts_known": len(known_conflicts)}
```

---

## Ảnh hưởng đến Data Hiện Tại (Parquet & Neo4j)

### Parquet hiện tại

Parquet hiện có (`documents.parquet`, `text_units.parquet`, `entities.parquet`, ...)
**không lưu metadata conflict** (vì đây là schema GraphRAG gốc). Cần một bước migration:

```python
def migrate_existing_parquet(workspace_output: Path, doc_registry: dict) -> None:
    """
    Thêm cột conflict metadata vào documents.parquet hiện tại.
    Không làm thay đổi các cột GraphRAG gốc → không cần re-index.
    """
    doc_path = workspace_output / "documents.parquet"
    df = pd.read_parquet(doc_path)

    # Thêm cột mới nếu chưa có
    for col, default in [
        ("status",              "active"),
        ("known_conflicts",     "[]"),
        ("conflict_resolved_by", None),
        ("indexed_at",          None),
        ("authority_level",     3),
        ("priority_score",      0.5),
        ("issued_date",         None),
    ]:
        if col not in df.columns:
            df[col] = default

    # Điền giá trị thực từ doc_registry nếu có
    for idx, row in df.iterrows():
        doc_id = row.get("id") or row.get("doc_id")
        if doc_id and doc_id in doc_registry:
            for col in ("status", "authority_level", "priority_score", "issued_date"):
                df.at[idx, col] = doc_registry[doc_id].get(col, df.at[idx, col])

    df.to_parquet(doc_path, index=False)
    print(f"[Migration] Đã cập nhật {len(df)} documents trong {doc_path}")
```

**Kết luận về parquet:** Migration nhẹ, chỉ thêm cột — **không re-index, không mất data, không tốn LLM**.

### Neo4j hiện tại

Neo4j hiện có: Document, TextUnit, Entity, Community, CommunityReport và quan hệ RELATED_TO.

Cần thêm:
1. **Property `status`** cho node Document → `SET d.status = 'active'` cho toàn bộ node hiện có
2. **Relationship `CONFLICTS_WITH`** → chỉ tạo khi có conflict mới phát hiện

```cypher
-- Migration Neo4j (chạy một lần)
MATCH (d:Document)
WHERE d.status IS NULL
SET d.status = 'active',
    d.authority_level = 3,
    d.priority_score = 0.5;

-- Tạo constraint cho conflict relationship
CREATE CONSTRAINT conflict_id IF NOT EXISTS
FOR ()-[r:CONFLICTS_WITH]-() REQUIRE r.conflict_id IS NOT NULL;
```

**Kết luận về Neo4j:** Migration an toàn, chỉ SET property còn thiếu và tạo constraint — **không xóa data, không re-index**.

---

## Mức Độ Khó Khi Triển Khai

| Hạng mục | Độ khó | Ghi chú |
|---|---|---|
| Migration parquet/Neo4j | ★☆☆ Dễ | Thêm cột/property, không re-index |
| Tích hợp hook vào `index_per_file.py` | ★☆☆ Dễ | Thêm ~30 dòng sau `run_command()` |
| `conflict_scanner.py` — logic cơ bản | ★★☆ Trung bình | Cần embedding batch + LLM mini-call |
| `_filter_candidate_docs` — tối ưu O(n) | ★★☆ Trung bình | Tránh O(n²), cần thiết kế filter hợp lý |
| Neo4j `CONFLICTS_WITH` edge | ★☆☆ Dễ | Thêm hàm `neo4j_merge_conflict()` |
| `conflict_registry` persistent store | ★★☆ Trung bình | Có thể dùng SQLite đơn giản hoặc JSON |
| Admin notification | ★☆☆ Dễ | Email/webhook Slack |
| **Tổng thể** | **★★☆ Trung bình** | Không yêu cầu thay đổi GraphRAG core |

---

## Conflict Registry Schema

File JSON đơn giản (hoặc SQLite) để query-time tra cứu nhanh:

```json
{
  "version": "2",
  "updated_at": "2025-01-15T10:30:00",
  "conflicts": [
    {
      "conflict_id": "conflict_abc123_def456",
      "doc_a": "abc123...",
      "doc_b": "def456...",
      "severity": "critical",
      "strategy": "authority_based",
      "winner_doc_id": "abc123...",
      "loser_doc_id": "def456...",
      "conflict_description": "Mức phạt lỗi X: 2.000.000đ vs 2.500.000đ",
      "detected_at": "2025-01-15T10:28:00",
      "resolved": true
    }
  ],
  "doc_status_overrides": {
    "def456...": "conflict_flagged"
  }
}
```

---

## Hành Vi Bắt Buộc

| # | Quy tắc | Áp dụng tại |
|---|---|---|
| 1 | Không bao giờ index mà bỏ qua bước duplicate hash check | Index-time |
| 2 | Luôn chạy conflict scan sau khi GraphRAG index xong | Index-time |
| 3 | Cập nhật `status` của loser doc ngay sau resolve | Index-time |
| 4 | Ghi `CONFLICTS_WITH` edge vào Neo4j | Index-time |
| 5 | Notify admin khi `strategy = needs_review` hoặc `severity = critical` | Index-time |
| 6 | Query-time chỉ đọc conflict_registry, không detect lại | Query-time |
| 7 | Không trả lời từ chunk có `status = deprecated` | Query-time |
| 8 | Cite nguồn và nêu conflict đã biết trong câu trả lời | Query-time |

---

## Lưu ý Triển Khai

- **Embedding model:** Dùng cùng model đã dùng khi index (thường `multilingual-e5-large` hoặc `bge-m3`) để đảm bảo cosine similarity nhất quán.
- **Ngưỡng similarity:** Bắt đầu với 0.75, điều chỉnh lên 0.80–0.85 cho văn bản pháp lý thuần túy sau khi quan sát false positive.
- **Chi phí LLM:** Mỗi lần index 1 file, số LLM call = số cặp (chunk_new, chunk_existing) vượt ngưỡng similarity. Dùng `_filter_candidate_docs` để giảm scope. Với corpus ~10 file, chi phí nhỏ.
- **Conflict registry:** Khởi đầu với JSON file đơn giản. Khi corpus lớn (>100 doc), migrate sang SQLite hoặc ghi thêm property vào Neo4j.
- **Không thay đổi GraphRAG core:** Toàn bộ logic v2 chạy ngoài GraphRAG, xen vào `index_per_file.py` — không cần fork hay sửa `packages/graphrag/`.

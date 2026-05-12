# Tính năng Phân tích Hợp đồng Lao động — Graph RAG Chatbot

> **Phạm vi:** Tài liệu này mô tả thiết kế, pipeline kỹ thuật, và các bước triển khai tính năng phân tích hợp đồng lao động tích hợp vào hệ thống Graph RAG pháp luật đã có.

---

## Mục lục

1. [Tổng quan tính năng](#1-tổng-quan-tính-năng)
2. [Kiến trúc tổng thể](#2-kiến-trúc-tổng-thể)
3. [Bước 1 — Tiếp nhận & Trích xuất Hợp đồng](#bước-1--tiếp-nhận--trích-xuất-hợp-đồng)
4. [Bước 2 — Phân tích Điều khoản (Clause Segmentation)](#bước-2--phân-tích-điều-khoản-clause-segmentation)
5. [Bước 3 — Entity & Relation Extraction](#bước-3--entity--relation-extraction)
6. [Bước 4 — Mapping Hợp đồng ↔ Knowledge Graph Pháp luật](#bước-4--mapping-hợp-đồng--knowledge-graph-pháp-luật)
7. [Bước 5 — Phát hiện Vi phạm & Rủi ro](#bước-5--phát-hiện-vi-phạm--rủi-ro)
8. [Bước 6 — Sinh Báo cáo Phân tích](#bước-6--sinh-báo-cáo-phân-tích)
9. [Bước 7 — Tích hợp Chatbot Q&A](#bước-7--tích-hợp-chatbot-qa)
10. [Schema Neo4j mở rộng](#schema-neo4j-mở-rộng)
11. [Prompt Templates](#prompt-templates)
12. [Đánh giá & Kiểm thử](#đánh-giá--kiểm-thử)
13. [Roadmap triển khai](#roadmap-triển-khai)

---

## 1. Tổng quan tính năng

### 1.1 Mục tiêu

Cho phép người dùng **upload hợp đồng lao động** (PDF/DOCX) và nhận được:


| Đầu ra                   | Mô tả                                                  |
| ------------------------ | ------------------------------------------------------ |
| **Phân tích điều khoản** | Liệt kê và giải thích từng điều khoản                  |
| **Cảnh báo vi phạm**     | Điều khoản trái với Bộ luật Lao động 2019              |
| **Điều khoản bất lợi**   | Thiệt thòi cho NLĐ nhưng không nhất thiết vi phạm luật |
| **Điều khoản còn thiếu** | Những nội dung bắt buộc nhưng HĐ không đề cập          |
| **Q&A tương tác**        | Hỏi đáp cụ thể về hợp đồng đã upload                   |


### 1.2 Người dùng mục tiêu

- **Người lao động (NLĐ):** Kiểm tra HĐ trước khi ký
- **Doanh nghiệp nhỏ:** Soạn HĐ đúng luật
- **Luật sư / HR:** Rà soát nhanh số lượng lớn HĐ

### 1.3 Phạm vi pháp lý

```
Bộ luật Lao động 2019 (Luật số 45/2019/QH14)
├── Chương III   — Hợp đồng lao động (Điều 13–58)
├── Chương V     — Tiền lương (Điều 90–100)
├── Chương VII   — Thời giờ làm việc, nghỉ ngơi (Điều 105–116)
└── Chương VIII  — Kỷ luật lao động (Điều 117–135)

Nghị định 145/2020/NĐ-CP — Hướng dẫn thi hành Bộ luật Lao động
Nghị định 38/2022/NĐ-CP  — Lương tối thiểu vùng (cập nhật hàng năm)
Thông tư 10/2020/TT-BLĐTBXH — Nội dung HĐ lao động
```

---

## 2. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│                      NGƯỜI DÙNG                              │
│              Upload HĐ (PDF/DOCX) + Câu hỏi                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  CONTRACT ANALYSIS PIPELINE                  │
│                                                             │
│  [1] Document Loader                                        │
│       └─ PDF/DOCX → Raw Text + Metadata                    │
│                                                             │
│  [2] Clause Segmenter                                       │
│       └─ Raw Text → Structured Clauses (JSON)              │
│                                                             │
│  [3] Entity & Relation Extractor                           │
│       └─ Clauses → Contract Knowledge Graph (temp)         │
│                                                             │
│  [4] Legal Mapper                                           │
│       └─ Contract Graph ↔ Neo4j Legal Graph                │
│                                                             │
│  [5] Violation Detector                                     │
│       └─ Mapping Results → Risk Report                     │
│                                                             │
│  [6] Report Generator                                       │
│       └─ Risk Report → Structured Analysis                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   ┌─────────────────┐       ┌─────────────────────┐
   │  Báo cáo PDF    │       │  Chatbot Q&A Engine  │
   │  (tóm tắt)      │       │  (hỏi đáp tương tác) │
   └─────────────────┘       └─────────────────────┘
```

---

## Bước 1 — Tiếp nhận & Trích xuất Hợp đồng

### 1.1 Các định dạng hỗ trợ


| Định dạng  | Thư viện              | Ghi chú                                |
| ---------- | --------------------- | -------------------------------------- |
| PDF (text) | `pdfplumber`, `pypdf` | Ưu tiên pdfplumber cho layout phức tạp |
| PDF (scan) | `PaddleOCR`           | OCR tiếng Việt, font Times New Roman   |
| DOCX       | `python-docx`         | Giữ lại cấu trúc heading               |
| Plain Text | Trực tiếp             | Fallback                               |


### 1.2 Preprocessing Pipeline

```python
class ContractLoader:
    def load(self, file_path: str) -> ContractDocument:
        """
        Output: ContractDocument
        {
            "raw_text": str,
            "pages": [{"page_num": 1, "text": "..."}],
            "metadata": {
                "filename": str,
                "total_pages": int,
                "detected_language": "vi",
                "contract_type": "labor" | "unknown"
            }
        }
        """
```

### 1.3 Kiểm tra sơ bộ

Sau khi load, thực hiện **contract type detection** để xác nhận đây là HĐLĐ:

```python
LABOR_CONTRACT_KEYWORDS = [
    "hợp đồng lao động", "người lao động", "người sử dụng lao động",
    "mức lương", "thời gian thử việc", "bảo hiểm xã hội",
    "thời giờ làm việc", "địa điểm làm việc"
]
# Nếu confidence < 0.6 → cảnh báo người dùng
```

---

## Bước 2 — Phân tích Điều khoản (Clause Segmentation)

### 2.1 Mục tiêu

Tách văn bản thô thành các **điều khoản có cấu trúc**, mỗi điều khoản tương ứng một chủ đề pháp lý.

### 2.2 Danh mục điều khoản cần phát hiện

```yaml
clause_categories:
  # Bắt buộc theo Điều 21 BLLĐ 2019
  mandatory:
    - PARTY_INFO          # Thông tin các bên
    - CONTRACT_TYPE       # Loại hợp đồng (xác định thời hạn / không thời hạn)
    - CONTRACT_DURATION   # Thời hạn hợp đồng
    - JOB_DESCRIPTION     # Công việc phải làm
    - WORKPLACE           # Địa điểm làm việc
    - WORKING_HOURS       # Thời giờ làm việc
    - SALARY              # Mức lương, hình thức trả lương
    - SOCIAL_INSURANCE    # BHXH, BHYT, BHTN
    - TRAINING            # Đào tạo, bồi dưỡng

  # Thường gặp, không bắt buộc
  common:
    - PROBATION           # Thử việc
    - ALLOWANCES          # Phụ cấp, trợ cấp
    - BONUS               # Thưởng
    - LEAVE               # Nghỉ phép
    - TERMINATION         # Chấm dứt hợp đồng
    - CONFIDENTIALITY     # Bảo mật thông tin
    - NON_COMPETE         # Không cạnh tranh
    - INTELLECTUAL_PROP   # Sở hữu trí tuệ
    - DISPUTE_RESOLUTION  # Giải quyết tranh chấp

  # Nhạy cảm, cần kiểm tra kỹ
  sensitive:
    - PENALTY_CLAUSE      # Phạt vi phạm
    - UNILATERAL_TERMS    # Điều khoản đơn phương có lợi cho NSDLĐ
    - WAIVER_CLAUSE       # Từ bỏ quyền lợi
```

### 2.3 Segmentation bằng LLM

```python
CLAUSE_SEGMENTATION_PROMPT = """
Bạn là chuyên gia phân tích hợp đồng lao động Việt Nam.
Hãy phân tích đoạn văn bản sau và trích xuất các điều khoản.

Với mỗi điều khoản, trả về JSON:
{
  "clause_id": "clause_001",
  "title": "Tiêu đề điều khoản",
  "category": "<một trong các category đã định nghĩa>",
  "original_text": "Văn bản gốc của điều khoản",
  "summary": "Tóm tắt ngắn gọn bằng ngôn ngữ đơn giản",
  "article_number": "Điều 3" // nếu có đánh số
}

Chỉ trả về JSON array, không giải thích thêm.

VĂN BẢN:
{contract_text}
"""
```

### 2.4 Output schema

```json
{
  "contract_id": "uuid",
  "clauses": [
    {
      "clause_id": "clause_001",
      "title": "Tiền lương",
      "category": "SALARY",
      "original_text": "Mức lương cơ bản là 5.000.000 VNĐ/tháng...",
      "summary": "Lương cơ bản 5 triệu/tháng, trả vào ngày 15 hàng tháng",
      "article_number": "Điều 5",
      "position": {"start_char": 1240, "end_char": 1580}
    }
  ],
  "missing_mandatory_clauses": ["SOCIAL_INSURANCE", "TRAINING"],
  "total_clauses": 12
}
```

---

## Bước 3 — Entity & Relation Extraction

### 3.1 Các loại Entity cần trích xuất

```
CONTRACT_ENTITY_TYPES = {
    # Chủ thể
    "EMPLOYEE"          : "Người lao động",
    "EMPLOYER"          : "Người sử dụng lao động",

    # Giá trị số
    "SALARY_VALUE"      : "Mức lương (VNĐ)",
    "DURATION_VALUE"    : "Thời hạn (tháng/năm)",
    "LEAVE_DAYS"        : "Số ngày phép",
    "WORKING_HOURS"     : "Giờ làm việc/tuần",
    "PROBATION_PERIOD"  : "Thời gian thử việc",
    "NOTICE_PERIOD"     : "Thời gian báo trước khi nghỉ",

    # Điều kiện
    "CONDITION"         : "Điều kiện kèm theo",
    "PENALTY"           : "Mức phạt vi phạm",
    "BENEFIT"           : "Quyền lợi phát sinh",

    # Tham chiếu pháp luật (nếu HĐ có trích dẫn)
    "LEGAL_REFERENCE"   : "Điều luật được trích dẫn"
}
```

### 3.2 Relations giữa các Entity

```
EMPLOYEE        --[KÝ_KẾT]-->        CONTRACT
EMPLOYER        --[KÝ_KẾT]-->        CONTRACT
CONTRACT        --[QUY_ĐỊNH]-->       SALARY_VALUE
CONTRACT        --[QUY_ĐỊNH]-->       WORKING_HOURS
CLAUSE          --[THUỘC]-->          CONTRACT
CLAUSE          --[ĐỀ_CẬP]-->        SALARY_VALUE
CLAUSE          --[ĐỀ_CẬP]-->        BENEFIT
CLAUSE          --[THAM_CHIẾU]-->     LEGAL_REFERENCE
```

### 3.3 Contract Graph (temporary, per-session)

```python
class ContractGraph:
    """
    Graph tạm thời cho một phiên phân tích.
    KHÔNG lưu vào Neo4j chính để tránh ô nhiễm knowledge base pháp luật.
    Lưu vào Neo4j với label riêng: :ContractSession
    """
    def build(self, clauses: list[Clause]) -> nx.DiGraph:
        ...

    def to_neo4j_session(self, session_id: str):
        # Tạo subgraph với prefix session_id
        # Tự động xóa sau 24h (TTL)
        ...
```

---

## Bước 4 — Mapping Hợp đồng ↔ Knowledge Graph Pháp luật

### 4.1 Chiến lược Mapping

Đây là bước **cốt lõi** kết nối hợp đồng với knowledge graph pháp luật đã index.

```
Với mỗi điều khoản trong hợp đồng:
    1. Vector search → tìm các điều luật liên quan nhất
    2. Graph traversal → mở rộng sang các điều luật liên kết
    3. Combine → tổng hợp context pháp lý đầy đủ
```

### 4.2 Cypher Queries cho Legal Graph

```cypher
// Query 1: Tìm điều luật liên quan đến tiền lương
MATCH (a:Article)-[:BELONGS_TO]->(c:Chapter)-[:PART_OF]->(l:Law)
WHERE a.keywords CONTAINS 'tiền lương'
  AND l.name CONTAINS 'Bộ luật Lao động'
RETURN a.article_number, a.content, a.summary
LIMIT 10

// Query 2: Lấy toàn bộ quy định về thử việc (có liên kết)
MATCH (a:Article {article_number: 'Điều 24'})-[r]->(related:Article)
RETURN a, r, related

// Query 3: Tìm nghị định hướng dẫn cho một điều luật cụ thể
MATCH (decree:Document)-[:GUIDES]->(article:Article {article_number: $article_num})
RETURN decree.name, decree.content
```

### 4.3 Mapping Logic

```python
class LegalMapper:
    def map_clause(self, clause: Clause) -> ClauseLegalMapping:
        """
        Với mỗi clause → tìm các điều luật liên quan
        """
        # Step 1: Semantic search trong vector store (LanceDB/parquet đã index)
        similar_articles = self.vector_store.search(
            query=clause.summary,
            filter={"doc_type": "labor_law"},
            top_k=5
        )

        # Step 2: Graph expansion trong Neo4j
        enriched = []
        for article in similar_articles:
            neighbors = self.neo4j.query("""
                MATCH (a:Article {id: $id})-[r:REFERENCES|AMENDS|GUIDES*1..2]-(related)
                RETURN related
            """, id=article.id)
            enriched.append({**article, "related_laws": neighbors})

        # Step 3: Rerank theo relevance
        return self.rerank(clause, enriched)
```

### 4.4 Mapping Result Schema

```json
{
  "clause_id": "clause_005",
  "clause_category": "SALARY",
  "mapped_laws": [
    {
      "article": "Điều 90 BLLĐ 2019",
      "content_summary": "Tiền lương do hai bên thỏa thuận...",
      "relevance_score": 0.94,
      "relationship": "DIRECTLY_GOVERNS"
    },
    {
      "article": "Điều 3 NĐ 38/2022",
      "content_summary": "Mức lương tối thiểu vùng I là 4.680.000 đ/tháng",
      "relevance_score": 0.87,
      "relationship": "SETS_MINIMUM"
    }
  ]
}
```

---

## Bước 5 — Phát hiện Vi phạm & Rủi ro

### 5.1 Phân loại mức độ rủi ro

```
🔴 VIOLATION    — Vi phạm pháp luật rõ ràng (có thể bị xử phạt)
🟠 HIGH_RISK    — Điều khoản bất lợi nghiêm trọng cho NLĐ
🟡 MEDIUM_RISK  — Điều khoản mơ hồ, dễ gây tranh chấp
🟢 COMPLIANT    — Tuân thủ pháp luật
⚪ NOT_COVERED  — Không có cơ sở pháp lý để đánh giá
```

### 5.2 Rule-based Detection (Fast Path)

Các vi phạm phổ biến có thể phát hiện bằng rule:

```python
VIOLATION_RULES = [
    {
        "rule_id": "VR001",
        "category": "SALARY",
        "severity": "VIOLATION",
        "description": "Mức lương thấp hơn lương tối thiểu vùng",
        "check": lambda clause, context:
            clause.salary_value < context.regional_minimum_wage,
        "legal_basis": "Điều 91 BLLĐ 2019 + NĐ 38/2022",
        "recommendation": "Mức lương phải ≥ {min_wage} đ/tháng (vùng {region})"
    },
    {
        "rule_id": "VR002",
        "category": "PROBATION",
        "severity": "VIOLATION",
        "description": "Thời gian thử việc vượt quá quy định",
        "check": lambda clause, context:
            clause.probation_days > context.max_probation_days,
        "legal_basis": "Điều 25 BLLĐ 2019",
        "recommendation": "Thử việc tối đa 180 ngày (quản lý) / 60 ngày / 30 ngày"
    },
    {
        "rule_id": "VR003",
        "category": "WORKING_HOURS",
        "severity": "VIOLATION",
        "description": "Giờ làm việc vượt quá 48h/tuần",
        "legal_basis": "Điều 105 BLLĐ 2019"
    },
    {
        "rule_id": "VR004",
        "category": "PROBATION",
        "severity": "HIGH_RISK",
        "description": "Lương thử việc dưới 85% lương chính thức",
        "legal_basis": "Điều 26 BLLĐ 2019"
    },
    {
        "rule_id": "VR005",
        "category": "CONTRACT_TYPE",
        "severity": "VIOLATION",
        "description": "Ký quá 2 lần HĐLĐ có thời hạn",
        "legal_basis": "Điều 20 BLLĐ 2019"
    },
    {
        "rule_id": "VR006",
        "category": "PENALTY_CLAUSE",
        "severity": "VIOLATION",
        "description": "Điều khoản phạt tiền NLĐ vi phạm nội quy",
        "legal_basis": "Điều 127 BLLĐ 2019 — cấm phạt tiền thay kỷ luật"
    }
]
```

### 5.3 LLM-based Detection (Deep Analysis)

Với các điều khoản phức tạp không thể rule-based:

```python
VIOLATION_DETECTION_PROMPT = """
Bạn là luật sư chuyên lao động Việt Nam với 10 năm kinh nghiệm.

ĐIỀU KHOẢN HỢP ĐỒNG:
{clause_text}

QUY ĐỊNH PHÁP LUẬT LIÊN QUAN:
{mapped_laws}

Hãy phân tích và trả về JSON:
{
  "is_violation": true/false,
  "severity": "VIOLATION|HIGH_RISK|MEDIUM_RISK|COMPLIANT",
  "issues": [
    {
      "issue_id": "I001",
      "description": "Mô tả vấn đề cụ thể",
      "legal_basis": "Điều ... BLLĐ 2019",
      "affected_party": "NLĐ|NSDLĐ|cả hai",
      "recommendation": "Đề xuất sửa đổi cụ thể"
    }
  ],
  "positive_aspects": ["Điểm tuân thủ tốt nếu có"],
  "confidence": 0.0-1.0
}

QUAN TRỌNG: Chỉ đưa ra cảnh báo có căn cứ pháp lý rõ ràng.
Không suy diễn ngoài phạm vi pháp luật.
"""
```

### 5.4 Missing Clause Detection

```python
MANDATORY_CLAUSES = {
    "PARTY_INFO":       "Điều 21.1a BLLĐ — Tên, địa chỉ các bên",
    "CONTRACT_TYPE":    "Điều 21.1b BLLĐ — Loại hợp đồng",
    "JOB_DESCRIPTION":  "Điều 21.1c BLLĐ — Công việc phải làm",
    "WORKPLACE":        "Điều 21.1d BLLĐ — Địa điểm làm việc",
    "CONTRACT_DURATION":"Điều 21.1đ BLLĐ — Thời hạn hợp đồng",
    "WORKING_HOURS":    "Điều 21.1e BLLĐ — Thời giờ làm việc, nghỉ ngơi",
    "SALARY":           "Điều 21.1g BLLĐ — Mức lương, hình thức trả lương",
    "SOCIAL_INSURANCE": "Điều 21.1h BLLĐ — Chế độ BHXH, BHYT",
    "TRAINING":         "Điều 21.1i BLLĐ — Đào tạo, bồi dưỡng nâng cao kỹ năng"
}
```

---

## Bước 6 — Sinh Báo cáo Phân tích

### 6.1 Cấu trúc báo cáo

```
BÁO CÁO PHÂN TÍCH HỢP ĐỒNG LAO ĐỘNG
─────────────────────────────────────
1. THÔNG TIN TỔNG QUAN
   - Tên file, ngày phân tích
   - Các bên ký kết
   - Loại hợp đồng, thời hạn

2. TỔNG KẾT ĐÁNH GIÁ (Dashboard)
   - Điểm tuân thủ tổng thể (0-100)
   - Số lượng vấn đề theo mức độ
   - Điều khoản bắt buộc còn thiếu

3. CHI TIẾT TỪNG ĐIỀU KHOẢN
   Với mỗi điều khoản:
   - Nội dung tóm tắt
   - Mức độ rủi ro
   - Cơ sở pháp lý
   - Khuyến nghị

4. CÁC VI PHẠM ƯU TIÊN XỬ LÝ
   - Danh sách vi phạm nghiêm trọng

5. ĐIỀU KHOẢN CÒN THIẾU
   - Liệt kê + cơ sở pháp lý bắt buộc

6. KHUYẾN NGHỊ TỔNG THỂ
```

### 6.2 Report Generator

```python
REPORT_GENERATION_PROMPT = """
Dựa trên kết quả phân tích sau, hãy viết báo cáo phân tích hợp đồng lao động
bằng ngôn ngữ dễ hiểu cho người không có chuyên môn pháp lý.

KẾT QUẢ PHÂN TÍCH:
{analysis_results}

YÊU CẦU:
- Giải thích vi phạm bằng ngôn ngữ đơn giản (tránh thuật ngữ pháp lý phức tạp)
- Luôn trích dẫn điều luật cụ thể
- Đưa ra khuyến nghị thực tế, có thể hành động ngay
- Ưu tiên những vấn đề quan trọng nhất
- Tone: chuyên nghiệp nhưng thân thiện, không gây hoảng loạn

OUTPUT FORMAT: Markdown với emoji biểu thị mức độ
"""
```

### 6.3 Compliance Score

```python
def calculate_compliance_score(analysis: ContractAnalysis) -> float:
    """
    Tính điểm tuân thủ (0-100):
    - Bắt đầu từ 100
    - Trừ điểm theo mức độ vi phạm:
        VIOLATION   : -15 điểm/vấn đề
        HIGH_RISK   : -8  điểm/vấn đề
        MEDIUM_RISK : -3  điểm/vấn đề
    - Trừ điểm thiếu điều khoản bắt buộc: -5/điều khoản
    - Min: 0
    """
```

---

## Bước 7 — Tích hợp Chatbot Q&A

### 7.1 Session Context Management

```python
class ContractQASession:
    """
    Lưu context hợp đồng cho một phiên hỏi đáp.
    """
    session_id: str
    contract_doc: ContractDocument
    clauses: list[Clause]
    analysis_results: AnalysisResult
    conversation_history: list[Message]
    expires_at: datetime  # TTL 2 giờ
```

### 7.2 Query Router

Phân loại câu hỏi của người dùng để chọn strategy phù hợp:

```python
QUERY_TYPES = {
    "SPECIFIC_CLAUSE":   # "Điều khoản lương của tôi có hợp lệ không?"
        → Tìm clause liên quan + mapped laws + trả lời cụ thể

    "RIGHTS_INQUIRY":    # "Tôi được hưởng bao nhiêu ngày phép?"
        → Extract từ clause + so sánh với quyền tối thiểu theo luật

    "VIOLATION_CHECK":   # "Hợp đồng có vi phạm gì không?"
        → Tổng hợp từ analysis_results

    "LEGAL_COMPARISON":  # "Thời gian thử việc như vậy có đúng luật không?"
        → So sánh với quy định pháp luật từ Knowledge Graph

    "GENERAL_ADVICE":    # "Tôi có nên ký hợp đồng này không?"
        → Tổng hợp toàn bộ phân tích + đưa ra khuyến nghị
}
```

### 7.3 RAG Query cho Contract Q&A

```python
CONTRACT_QA_PROMPT = """
Bạn là trợ lý pháp lý chuyên về luật lao động Việt Nam.
Người dùng đã upload một hợp đồng lao động và đang hỏi về nó.

THÔNG TIN HỢP ĐỒNG LIÊN QUAN:
{relevant_clauses}

QUY ĐỊNH PHÁP LUẬT LIÊN QUAN:
{legal_context}

KẾT QUẢ PHÂN TÍCH (nếu có):
{analysis_summary}

LỊCH SỬ HỘI THOẠI:
{conversation_history}

CÂU HỎI HIỆN TẠI: {user_question}

HƯỚNG DẪN TRẢ LỜI:
1. Trả lời trực tiếp vào câu hỏi
2. Trích dẫn điều khoản hợp đồng + điều luật cụ thể
3. Nếu không tìm thấy thông tin trong HĐ → nói rõ
4. Đưa ra cảnh báo nếu phát hiện vấn đề
5. KHÔNG bịa đặt thông tin không có trong tài liệu
6. Khuyến nghị tham vấn luật sư nếu vấn đề phức tạp
"""
```

---

## Schema Neo4j mở rộng

### Nodes mới cho Contract Analysis

```cypher
// Node cho phiên phân tích (tạm thời, có TTL)
CREATE (s:ContractSession {
    session_id: $session_id,
    created_at: datetime(),
    expires_at: datetime() + duration({hours: 24}),
    contract_filename: $filename,
    compliance_score: $score
})

// Node cho điều khoản hợp đồng
CREATE (c:ContractClause {
    clause_id: $clause_id,
    session_id: $session_id,
    category: $category,
    title: $title,
    original_text: $text,
    summary: $summary,
    severity: $severity  // VIOLATION|HIGH_RISK|MEDIUM_RISK|COMPLIANT
})

// Node cho vấn đề phát hiện
CREATE (i:ContractIssue {
    issue_id: $issue_id,
    description: $description,
    severity: $severity,
    legal_basis: $legal_basis,
    recommendation: $recommendation
})
```

### Relationships mới

```cypher
// Session → Clause
(session:ContractSession)-[:CONTAINS_CLAUSE]->(clause:ContractClause)

// Clause ↔ Law Article (kết nối với Legal Graph hiện có)
(clause:ContractClause)-[:GOVERNED_BY {relevance_score: 0.94}]->(article:Article)
(clause:ContractClause)-[:VIOLATES]->(article:Article)

// Clause → Issue
(clause:ContractClause)-[:HAS_ISSUE]->(issue:ContractIssue)

// Issue → Article (căn cứ pháp lý)
(issue:ContractIssue)-[:BASED_ON]->(article:Article)
```

### Index cho performance

```cypher
CREATE INDEX contract_session_id FOR (s:ContractSession) ON (s.session_id);
CREATE INDEX contract_clause_session FOR (c:ContractClause) ON (c.session_id);
CREATE INDEX contract_clause_category FOR (c:ContractClause) ON (c.category);
```

---

## Prompt Templates

### Template 1: Entity Extraction (tiếng Việt)

```python
ENTITY_EXTRACTION_PROMPT = """
Trích xuất thông tin từ điều khoản hợp đồng lao động sau.
Trả về JSON ONLY, không giải thích.

ĐIỀU KHOẢN:
{clause_text}

OUTPUT JSON:
{
  "entities": [
    {
      "type": "SALARY_VALUE|DURATION_VALUE|LEAVE_DAYS|...",
      "value": "giá trị cụ thể",
      "unit": "VNĐ/tháng|ngày|giờ/tuần|...",
      "raw_text": "đoạn văn gốc chứa giá trị này"
    }
  ],
  "conditions": ["Điều kiện đi kèm nếu có"],
  "obligations": {
    "employee": ["Nghĩa vụ của NLĐ"],
    "employer": ["Nghĩa vụ của NSDLĐ"]
  }
}
"""
```

### Template 2: Compliance Check

```python
COMPLIANCE_CHECK_PROMPT = """
Kiểm tra tính hợp pháp của điều khoản sau theo pháp luật lao động Việt Nam.

ĐIỀU KHOẢN CẦN KIỂM TRA:
Tiêu đề: {clause_title}
Nội dung: {clause_text}
Giá trị trích xuất: {extracted_values}

QUY ĐỊNH PHÁP LUẬT ÁP DỤNG:
{legal_articles}

NGƯỠNG PHÁP ĐỊNH (cập nhật {current_year}):
- Lương tối thiểu vùng I: 4.960.000 đ/tháng
- Lương tối thiểu vùng II: 4.410.000 đ/tháng
- Lương tối thiểu vùng III: 3.860.000 đ/tháng
- Lương tối thiểu vùng IV: 3.450.000 đ/tháng
- Giờ làm tối đa: 48h/tuần, 8h/ngày (thông thường)
- Thử việc tối đa: 180 ngày (quản lý cấp cao), 60 ngày (đại học trở lên), 30 ngày (khác)
- Lương thử việc: ≥ 85% lương chính thức

Hãy phân tích và đưa ra kết luận.
"""
```

---

## Đánh giá & Kiểm thử

### 8.1 Test Cases cần có

```
tests/
├── unit/
│   ├── test_contract_loader.py       # Load PDF/DOCX chính xác
│   ├── test_clause_segmenter.py      # Tách điều khoản đúng
│   ├── test_entity_extractor.py      # Trích xuất entity chính xác
│   └── test_violation_rules.py       # Rule-based detection
│
├── integration/
│   ├── test_legal_mapping.py         # Mapping với Neo4j
│   └── test_end_to_end.py            # Pipeline toàn bộ
│
└── fixtures/
    ├── sample_contracts/
    │   ├── valid_contract.pdf         # HĐ hợp lệ hoàn toàn
    │   ├── contract_with_violations.pdf  # HĐ có vi phạm rõ ràng
    │   ├── contract_missing_clauses.pdf  # HĐ thiếu điều khoản bắt buộc
    │   └── scanned_contract.pdf       # HĐ scan (test OCR)
    └── expected_outputs/
        ├── valid_contract_analysis.json
        └── violations_contract_analysis.json
```

### 8.2 Metrics đánh giá


| Metric                 | Target | Mô tả                                             |
| ---------------------- | ------ | ------------------------------------------------- |
| Clause Detection F1    | ≥ 0.85 | Phát hiện đúng điều khoản                         |
| Violation Precision    | ≥ 0.90 | Cảnh báo vi phạm chính xác (tránh false positive) |
| Violation Recall       | ≥ 0.80 | Không bỏ sót vi phạm nghiêm trọng                 |
| Legal Mapping Accuracy | ≥ 0.85 | Map đúng điều luật                                |
| Response Latency       | ≤ 30s  | Thời gian phân tích toàn bộ HĐ                    |

---

## Phụ lục — Cấu trúc thư mục gợi ý

```
contract_analysis/
├── __init__.py
├── loader/
│   ├── pdf_loader.py
│   ├── docx_loader.py
│   └── ocr_loader.py
├── segmenter/
│   └── clause_segmenter.py
├── extractor/
│   └── entity_extractor.py
├── mapper/
│   ├── legal_mapper.py
│   └── cypher_queries.py
├── detector/
│   ├── rule_detector.py       # Rule-based (fast)
│   ├── llm_detector.py        # LLM-based (deep)
│   └── violation_rules.py     # Định nghĩa rules
├── reporter/
│   └── report_generator.py
├── qa/
│   ├── session_manager.py
│   ├── query_router.py
│   └── contract_qa.py
├── schemas/
│   ├── contract_models.py     # Pydantic models
│   └── neo4j_schemas.py
└── prompts/
    └── templates.py
```


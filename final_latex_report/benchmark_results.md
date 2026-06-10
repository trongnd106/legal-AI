# Kết Quả Thực Nghiệm — GraphRAG Luật Lao Động VN

> **Hướng dẫn sử dụng:**
> - Mỗi bảng có `<!-- RUN: ... -->` chỉ rõ lệnh tạo ra số liệu.
> - Điền số thực vào các ô `—`.
> - Sau khi điền đủ, chuyển sang LaTeX tương ứng trong `4_Ket_qua_thuc_nghiem.tex`.

---

## Phân loại câu hỏi benchmark

Bộ câu hỏi được chia theo **loại câu hỏi pháp lý** (ngữ nghĩa), kèm nhãn kỹ thuật phụ.
Mỗi loại có một search mode được thiết kế phù hợp nhất — benchmark sẽ chạy **tất cả mode trên cùng một bộ câu hỏi** để so sánh.

| Loại câu hỏi | Ký hiệu | Search mode phù hợp | Nhãn kỹ thuật | Số câu đề xuất |
|---|:---:|---|---|:---:|
| **Tra cứu điều luật** | TK | local_search | single_hop | 20 |
| **Tổng quan / chính sách** | TQ | global_search | single_hop / comparative | 10 |
| **Tình huống thực tế** | TH | local + multihop | multi_hop | 15 |
| **Suy luận đa văn bản** | SL | local + multihop | multi_hop / cross_domain | 10 |
| **Hiệu lực văn bản** | HL | local + temporal filter | temporal | 8 |
| **Ngoài phạm vi** (negative) | NP | — (should refuse) | out_of_scope | 5 |
| **Tổng** | | | | **68** |

> *Negative cases (NP) không tính vào accuracy chính — chỉ đo tỷ lệ hệ thống từ chối trả lời đúng.*

---

## 4.4.1 Kết quả Indexing (§4.4.1)

<!-- RUN: python scripts/03_inspect_output.py  /  đọc data/labor-law/output/stats.json -->

### Bảng 4.1 — Thống kê Corpus và Knowledge Graph sau Index

| Hạng mục | Giá trị |
|---|---|
| Số văn bản pháp luật | 7 |
| Tổng số Điều (documents) | 581 |
| Tổng số Khoản | 2 069 |
| Tổng số Điểm | 1 705 |
| **Graph L1 — Structural** | |
| Nodes L1 (VanBan, Dieu, Khoan, Chuong) | — |
| Relationships L1 | — |
| **Graph L2 — Semantic (LLM-extracted)** | |
| Entity types (ChuThe, HanhVi, TienLuong, ...) | 14 |
| Entities L2 | — |
| Relationships L2 | — |
| Communities (level 0) | — |
| Communities (level 1) | — |
| Communities (level 2) | — |
| **Chi phí Indexing** | |
| Tổng thời gian index (s) | — *(~524 s đã ghi nhận)* |
| Thời gian extract\_graph (s) | — *(~159 s đã ghi nhận)* |
| Ước tính LLM calls | — *(~4 000–5 000)* |
| Ước tính tokens tiêu thụ | — *(~10–12 M)* |
| Cache hit rate (re-index) | — |

---

## 4.4.2 So Sánh Hiệu Quả Tổng Thể (§4.4.2)

### E1 — So sánh tổng thể trên toàn bộ bộ câu hỏi

<!-- RUN: python tests/evaluation_suite.py -->
<!-- RUN: python scripts/ragas_graphrag_benchmark.py --root data/labor-law --method local|global|basic|drift --questions scripts/qa_questions.json -->
<!-- RUN: python scripts/baseline_zeroshot.py -->

#### Bảng 4.2 — So sánh các phương pháp (n = ___ câu hỏi, 5 loại TK/TQ/TH/SL/HL)

| Phương pháp | Keyword Acc. | Citation Acc. | Faithfulness | Answer Rel. | Ghi chú |
|---|:---:|:---:|:---:|:---:|---|
| **Zero-shot LLM** (Baseline 0) | — | — | — | — | Không RAG |
| **Basic Search** (Baseline 1) | — | — | — | — | Vector RAG thuần |
| **Local Search** | — | — | — | — | GraphRAG entity-centric |
| **Global Search** | — | — | — | — | Map-reduce community |
| **DRIFT Search** | — | — | — | — | Iterative follow-up |
| **Local + Multihop** | — | — | — | — | Custom KG traversal |

*Faithfulness, Answer Relevancy: thang 0–1, judge bởi Gemini 2.0 Flash (RAGAS).*
*Keyword Acc., Citation Acc.: thang 0–1, tính bởi `evaluation_suite.py`.*

---

## 4.4.3 Phân Tích theo Loại Câu Hỏi (§4.4.3)

### Bảng 4.3 — Keyword Accuracy theo Loại câu hỏi × Phương pháp

<!-- RUN: python tests/evaluation_suite.py (đọc kết quả by_category, map sang loại mới) -->

| Loại câu hỏi | Mode phù hợp | Số câu | Zero-shot | Basic | Local | Global | Multihop |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| TK — Tra cứu điều luật | local | 20 | — | — | — | — | — |
| TQ — Tổng quan / chính sách | global | 10 | — | — | — | — | — |
| TH — Tình huống thực tế | local+multihop | 15 | — | — | — | — | — |
| SL — Suy luận đa văn bản | local+multihop | 10 | — | — | — | — | — |
| HL — Hiệu lực văn bản | local+filter | 8 | — | — | — | — | — |
| **Tổng** | | **63** | — | — | — | — | — |

> *Đọc kết quả: mỗi hàng cho thấy loại câu hỏi nào mode nào xử lý tốt nhất → chứng minh thiết kế đúng mục đích.*

### Bảng 4.4 — Citation Accuracy theo Loại câu hỏi × Phương pháp

| Loại câu hỏi | Số câu | Basic | Local | Global | Multihop |
|---|:---:|:---:|:---:|:---:|:---:|
| TK — Tra cứu điều luật | 20 | — | — | — | — |
| TQ — Tổng quan / chính sách | 10 | — | — | — | — |
| TH — Tình huống thực tế | 15 | — | — | — | — |
| SL — Suy luận đa văn bản | 10 | — | — | — | — |
| HL — Hiệu lực văn bản | 8 | — | — | — | — |

### Bảng 4.5 — Hành vi trên câu hỏi Ngoài phạm vi (Negative cases)

<!-- Đánh giá thủ công: hệ thống có từ chối / cảnh báo không? -->

| Phương pháp | Từ chối đúng | Trả lời sai (hallucinate) | Ghi chú |
|---|:---:|:---:|---|
| Zero-shot LLM | — / 5 | — / 5 | |
| Basic Search | — / 5 | — / 5 | |
| Local Search | — / 5 | — / 5 | |
| Global Search | — / 5 | — / 5 | |

---

## 4.4.4 Thí nghiệm So sánh theo Loại câu hỏi (§4.4.3 mở rộng)

### E2 — Tra cứu điều luật (TK): Local vs Basic

<!-- Câu hỏi TK phù hợp nhất với local_search — thí nghiệm này chứng minh điều đó -->

#### Bảng 4.6 — TK: Vector RAG vs GraphRAG Local (n = 20 câu)

| Phương pháp | Keyword Acc. | Citation Acc. | Avg Latency (s) |
|---|:---:|:---:|:---:|
| Basic Search | — | — | — |
| Local Search | — | — | — |
| Cải thiện (Local − Basic) | **+—** | **+—** | — |

### E3 — Tổng quan / chính sách (TQ): Local vs Global

<!-- Câu hỏi TQ phù hợp nhất với global_search — community reports tổng hợp tốt hơn -->

#### Bảng 4.7 — TQ: Local vs Global Search (n = 10 câu)

| Phương pháp | Keyword Acc. | Answer Relevancy | Avg Latency (s) |
|---|:---:|:---:|:---:|
| Local Search | — | — | — |
| Global Search | — | — | — |
| Cải thiện (Global − Local) | **+—** | **+—** | — *(global chậm hơn)* |

### E4 — Tình huống + Suy luận đa văn bản (TH + SL): Local vs Multihop

<!-- Câu hỏi TH/SL đòi hỏi suy luận qua nhiều Điều → multihop tốt hơn local đơn thuần -->

#### Bảng 4.8 — TH+SL: Local vs Local+Multihop (n = 25 câu)

| Phương pháp | Keyword Acc. | Citation Acc. | Reasoning Chain Hit | Avg Latency (s) |
|---|:---:|:---:|:---:|:---:|
| Local Search | — | — | — | — |
| Local + Multihop | — | — | — | — |
| Cải thiện | **+—** | **+—** | **+—** | — |

*Reasoning Chain Hit: % câu trả lời đề cập đủ các Điều trong chuỗi suy luận (ví dụ: Điều 35 → Điều 46).*

### E5 — Hiệu lực văn bản (HL): Có vs Không có Temporal Filter

<!-- Câu hỏi HL kiểm tra hệ thống có trả về đúng văn bản đang hiệu lực không -->

#### Bảng 4.9 — HL: Local Search với và không có Temporal Filter (n = 8 câu)

| Cấu hình | Keyword Acc. | Trả lời đúng văn bản hiệu lực | Ghi chú |
|---|:---:|:---:|---|
| Local (không filter) | — | — / 8 | Có thể trả về NĐ 90/2019 đã hết hiệu lực |
| Local + Temporal Filter | — | — / 8 | Chỉ trả NĐ 74/2024 đang hiệu lực |

---

## 4.4.5 Case Study Chi Tiết (§4.4.4)

<!-- Điền thủ công: copy câu trả lời thực từ hệ thống, cắt ngắn nếu cần -->

### Case A — TK: Tra cứu Điều 27 (thử việc 60 ngày)

| Hạng mục | Nội dung |
|---|---|
| Loại câu hỏi | TK — Tra cứu điều luật |
| Câu hỏi | Thời gian thử việc tối đa với công việc đòi hỏi trình độ chuyên môn là bao lâu? |
| Ground truth | 60 ngày, Điều 27 BLLĐ 2019 |
| **Basic Search** — trả lời | *[điền sau khi chạy]* |
| Basic — kw_hit / cite_hit | — / — |
| **Local Search** — trả lời | *[điền sau khi chạy]* |
| Local — kw_hit / cite_hit | — / — |
| Nhận xét | — |

### Case B — TQ: Tổng quan quy định chấm dứt HĐLĐ

| Hạng mục | Nội dung |
|---|---|
| Loại câu hỏi | TQ — Tổng quan / chính sách |
| Câu hỏi | Tóm tắt các trường hợp NSDLĐ được đơn phương chấm dứt HĐLĐ hợp pháp |
| Ground truth | Điều 36 BLLĐ 2019 (7 trường hợp) |
| **Local Search** — trả lời | *[điền sau khi chạy]* |
| Local — kw_hit / cite_hit | — / — |
| **Global Search** — trả lời | *[điền sau khi chạy]* |
| Global — kw_hit / cite_hit | — / — |
| Nhận xét | — |

### Case C — TH: Tình huống NLĐ đơn phương chấm dứt + trợ cấp

| Hạng mục | Nội dung |
|---|---|
| Loại câu hỏi | TH — Tình huống thực tế |
| Câu hỏi | NLĐ đơn phương chấm dứt đúng pháp luật có được trợ cấp thôi việc không và cần điều kiện gì? |
| Reasoning chain | Điều 35 (quyền đơn phương) → Điều 46 (trợ cấp thôi việc) |
| **Local Search** — trả lời | *[điền sau khi chạy]* |
| Local — kw_hit / chain_hit | — / — |
| **Local + Multihop** — trả lời | *[điền sau khi chạy]* |
| Multihop — kw_hit / chain_hit | — / — |
| Nhận xét | — |

### Case D — SL: Suy luận đa văn bản — lương tối thiểu → phạt NĐ 12/2022

| Hạng mục | Nội dung |
|---|---|
| Loại câu hỏi | SL — Suy luận đa văn bản |
| Câu hỏi | Công ty trả lương dưới mức tối thiểu vùng IV thì bị phạt bao nhiêu? |
| Reasoning chain | Điều 90 BLLĐ (nghĩa vụ trả lương) → NĐ 12/2022 Điều 17 (mức phạt) |
| **Local Search** — trả lời | *[điền sau khi chạy]* |
| Local — chain resolved | — |
| **Local + Multihop** — trả lời | *[điền sau khi chạy]* |
| Multihop — chain resolved | — |
| Nhận xét | — |

### Case E — HL: Hiệu lực văn bản — NĐ lương tối thiểu

| Hạng mục | Nội dung |
|---|---|
| Loại câu hỏi | HL — Hiệu lực văn bản |
| Câu hỏi | Nghị định quy định lương tối thiểu vùng đang có hiệu lực là nghị định nào? |
| Ground truth | NĐ 74/2024/NĐ-CP (NĐ 90/2019 đã hết hiệu lực) |
| **Local (không filter)** — trả lời | *[điền sau khi chạy]* |
| Có nhắc NĐ hết hiệu lực không | — |
| **Local + Temporal Filter** — trả lời | *[điền sau khi chạy]* |
| Trả lời đúng NĐ hiệu lực | — |
| Nhận xét | — |

### Case F — E5: Contract Analysis — HĐLĐ mẫu vi phạm lương

| Hạng mục | Nội dung |
|---|---|
| File test | hdld_sample_01.docx |
| Số điều khoản tách được | — |
| Rules triggered | *(ví dụ: VR001, VR005, VR007)* |
| Compliance score | — / 100 |
| Ground truth violations | *[điền từ annotation]* |
| TP / FP / FN | — / — / — |
| Thời gian xử lý (s) | — |
| Nhận xét | — |

---

## 4.4.6 Contract Analysis: Precision / Recall / F1 (§4.4.2 mở rộng)

<!-- RUN: python scripts/contract_benchmark.py (cần viết) -->

### Bảng 4.10 — Phân tích vi phạm hợp đồng (n = ___ HĐLĐ mẫu)

| Rule | Mô tả vi phạm | TP | FP | FN | Precision | Recall | F1 |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| VR001 | Lương < mức tối thiểu vùng | — | — | — | — | — | — |
| VR002 | Thiếu / sai loại HĐLĐ | — | — | — | — | — | — |
| VR003 | Giờ làm vượt 8 h/ngày | — | — | — | — | — | — |
| VR004 | Làm thêm vượt 200 h/năm | — | — | — | — | — | — |
| VR005 | Điều khoản phạt tiền NLĐ | — | — | — | — | — | — |
| VR006 | Thử việc vượt giới hạn | — | — | — | — | — | — |
| VR007 | Thiếu điều khoản bắt buộc | — | — | — | — | — | — |
| VR008–VR016 | *(các rule còn lại)* | — | — | — | — | — | — |
| **Aggregate** | | — | — | — | **—** | **—** | **—** |

### Bảng 4.11 — Latency pipeline phân tích hợp đồng

| Bước | Thời gian TB (s) | Ghi chú |
|---|:---:|---|
| Load + OCR | — | PDF scan chậm hơn DOCX |
| Segment (LLM) | — | |
| Apply rules | — | < 5 ms/clause |
| Map → luật (multihop) | — | concurrency=4 |
| LLM review batch | — | Chỉ complex categories |
| Finalize report | — | |
| **Tổng end-to-end** | — | File ~5 trang |

---

## 4.4.7 Hiệu Năng và Chi Phí (§4.4.5)

### Bảng 4.12 — Latency Query theo Phương pháp (P50 / P95)

<!-- RUN: đo 10 lần × 5 câu đại diện mỗi mode -->

| Phương pháp | P50 (ms) | P95 (ms) | Avg Input Tokens | Avg Output Tokens | Est. Cost / query (USD) |
|---|:---:|:---:|:---:|:---:|:---:|
| Zero-shot LLM | — | — | — | — | — |
| Basic Search | — | — | — | — | — |
| Local Search | — | — | — | — | — |
| Global Search | — | — | — | — | — |
| DRIFT Search | — | — | — | — | — |
| Local + Multihop | — | — | — | — | — |

### Bảng 4.13 — Trade-off Chất lượng vs Tốc độ vs Chi phí

| Phương pháp | Keyword Acc. | Latency P95 (ms) | Chi phí tương đối | Phù hợp cho loại câu hỏi |
|---|:---:|:---:|:---:|---|
| Basic Search | — | — | Thấp | TK đơn giản, cần tốc độ |
| Local Search | — | — | Trung bình | TK, TH cơ bản |
| Global Search | — | — | Cao | TQ — tổng quan, chính sách |
| Local + Multihop | — | — | Trung bình | TH, SL — suy luận đa bước |
| Local + Filter | — | — | Trung bình | HL — hiệu lực văn bản |

---

## 4.5 So sánh và Thảo luận (§4.5)

### Bảng 4.14 — Hệ thống vs GraphRAG gốc (Microsoft)

| Đặc điểm | GraphRAG gốc | Hệ thống tùy biến | Cải tiến |
|---|---|---|---|
| Ontology | Generic entity types | 14 types domain lao động + L1 structural | Domain-specific extraction |
| Citation | Không | Điều/Khoản cụ thể (L1 deterministic) | Trích dẫn pháp lý chính xác |
| Temporal filter | Không | Lọc theo hiệu lực văn bản (metadata.json) | Không trả về luật hết hiệu lực |
| Rule validator | Không | VR001–VR016 (contract analysis) | Phát hiện vi phạm tự động |
| Multi-hop | Community reports | Custom KG traversal (L1+L2 merged) | Suy luận chuỗi Điều–Điều |
| Faithfulness | — | — | *(điền sau khi đo)* |

### Bảng 4.15 — Hạn chế thực nghiệm

| Hạn chế | Mức độ ảnh hưởng | Hướng khắc phục |
|---|---|---|
| Corpus hẹp (chỉ lao động + BHXH) | Cao | Mở rộng corpus dân sự, doanh nghiệp |
| Ground truth chưa được luật sư review | Trung bình | Validate với chuyên gia pháp lý |
| RAGAS chỉ dùng Gemini làm judge | Thấp | Thêm GPT-4o judge để cross-validate |
| Chưa đo inter-annotator agreement | Trung bình | Annotation 2 người, tính Cohen's kappa |

---

## Appendix — Bộ câu hỏi benchmark

> File đầy đủ: `scripts/qa_benchmark_questions.json`

### Danh sách câu hỏi (n = ___)

| ID | Loại | Nhãn kỹ thuật | Câu hỏi | Expected Citations |
|---|:---:|---|---|---|
| TK001 | TK | single_hop | Thời gian thử việc tối đa với trình độ chuyên môn? | Điều 27 |
| TK002 | TK | single_hop | Người lao động có bao nhiêu ngày nghỉ phép năm tối thiểu? | Điều 113 |
| TK003 | TK | single_hop | Lương tối thiểu vùng I hiện tại là bao nhiêu? | Điều 91 |
| TK004 | TK | single_hop | NLĐ được nghỉ bao nhiêu ngày khi kết hôn? | Điều 115 |
| TK… | TK | single_hop | *(thêm 16 câu tra cứu)* | … |
| TQ001 | TQ | comparative | Tóm tắt các trường hợp NSDLĐ được đơn phương chấm dứt HĐLĐ | Điều 36 |
| TQ002 | TQ | comparative | Sự khác biệt giữa HĐLĐ có thời hạn và không thời hạn? | Điều 20 |
| TQ… | TQ | comparative | *(thêm 8 câu tổng quan)* | … |
| TH001 | TH | multi_hop | NLĐ đơn phương chấm dứt đúng luật, điều kiện + trợ cấp? | Điều 35, Điều 46 |
| TH002 | TH | multi_hop | NSDLĐ không trả trợ cấp thôi việc bị xử lý thế nào? | Điều 46, NĐ 12/2022 |
| TH… | TH | multi_hop | *(thêm 13 câu tình huống)* | … |
| SL001 | SL | cross_domain | Công ty trả lương dưới mức tối thiểu vùng IV bị phạt bao nhiêu? | NĐ 12/2022 |
| SL002 | SL | cross_domain | Không đóng BHXH → phạt hành chính + hình sự thế nào? | Điều 216 BLHS |
| SL… | SL | cross_domain | *(thêm 8 câu suy luận)* | … |
| HL001 | HL | temporal | NĐ lương tối thiểu đang hiệu lực là NĐ nào? | NĐ 74/2024 |
| HL002 | HL | temporal | NĐ 90/2019 có còn hiệu lực không? | — |
| HL… | HL | temporal | *(thêm 6 câu hiệu lực)* | … |
| NP001 | NP | out_of_scope | Mức phạt về tội trốn thuế là bao nhiêu? | — |
| NP… | NP | out_of_scope | *(thêm 4 câu ngoài phạm vi)* | … |

---

*Cập nhật lần cuối: ___/___/2026 — Người điền: ___*

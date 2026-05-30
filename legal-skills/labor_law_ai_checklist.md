# Checklist: Trợ lý Ảo Luật Lao Động Việt Nam (GraphRAG)

> **Stack**: Microsoft GraphRAG (Python) · **Domain**: Bộ luật Lao động 2019 + các Nghị định hướng dẫn  
> **Mục tiêu**: Chuyển từ RAG thuần vector sang Knowledge Graph có khả năng multi-hop reasoning  
> **Trạng thái**: ☐ Chưa thực hiện · ⚙️ Đang làm · ✅ Hoàn thành

---

## Phần 1 — Thu thập & Chuẩn hóa dữ liệu Luật Lao động

| # | Hạng mục | File hướng dẫn | Trạng thái |
|---|----------|---------------|-----------|
| 1.1 | Thu thập văn bản: Bộ luật Lao động 2019 (45/2019/QH14) từ vbpl.vn | `legal-skills/01_data_collection.md` | ☐ |
| 1.2 | Thu thập các Nghị định hướng dẫn chính: NĐ 145/2020, NĐ 12/2022, NĐ 38/2022 | `legal-skills/01_data_collection.md` | ☐ |
| 1.3 | Phân tách cấu trúc phân cấp: Phần → Chương → Mục → Điều → Khoản → Điểm | `legal-skills/02_ontology_design.md` | ✅ |
| 1.4 | Chuẩn hóa text: bỏ header/footer, chuẩn hóa encoding UTF-8, tách file theo Điều | `legal-skills/01_data_collection.md` | ✅ |
| 1.5 | Xây dựng metadata mapping: ngày ban hành, ngày hiệu lực, tình trạng hiệu lực | `legal-skills/02_ontology_design.md` | ✅ |

---

## Phần 2 — Thiết kế Ontology Luật Lao động

| # | Hạng mục | File hướng dẫn | Trạng thái |
|---|----------|---------------|-----------|
| 2.1 | Định nghĩa entity types: `VanBan`, `Chuong`, `Dieu`, `Khoan`, `Diem`, `CoQuan`, `ChuThe`, `HanhVi` | `legal-skills/02_ontology_design.md` | ✅ |
| 2.2 | Định nghĩa semantic entities đặc thù lao động: `HopDongLaoDong`, `TienLuong`, `ThoiGioLamViec`, `NghiPhep`, `TraLuong`, `XuLyKyLuat`, `CheDoBaoHiem`, `TroCapThoiViec`, `CheTai`, `AnToanVeSinhLaoDong` | `legal-skills/02_ontology_design.md` | ✅ |
| 2.3 | Định nghĩa relation types: `contains`, `cites`, `amends`, `repeals`, `obligates`, `entitles`, `prohibits`, `regulates`, `penalizes`, `disciplines`, `enforced_by`, `issued_by`, `guided_by` | `legal-skills/02_ontology_design.md` | ✅ |
| 2.4 | Gắn nhãn loại quy phạm: `nghia_vu` (NLĐ/NSDLĐ phải), `quyen` (NLĐ/NSDLĐ được), `cam_doan` (không được), `thu_tuc` | `legal-skills/02_ontology_design.md` | ✅ |
| 2.5 | Schema JSON/YAML cho GraphRAG entity config (`settings.yaml` → `entity_extraction`) | `legal-skills/02_ontology_design.md` | ✅ |

---

## Phần 3 — Xây dựng Knowledge Graph với GraphRAG

| # | Hạng mục | File hướng dẫn | Trạng thái |
|---|----------|---------------|-----------|
| 3.1 | Cấu hình `graphrag init` cho corpus luật lao động | `legal-skills/03_graphrag_pipeline.md` | ☐ |
| 3.2 | Tùy chỉnh entity extraction prompt cho domain luật lao động (tiếng Việt) | `legal-skills/03_graphrag_pipeline.md` | ☐ |
| 3.3 | Tùy chỉnh relationship extraction prompt: nhận dạng `cites`, `amends`, `obligates`, `prohibits` | `legal-skills/03_graphrag_pipeline.md` | ☐ |
| 3.4 | Cấu hình chunking strategy: ưu tiên tách theo Khoản, không cắt giữa câu pháp lý | `legal-skills/03_graphrag_pipeline.md` | ☐ |
| 3.5 | Chạy indexing pipeline: `graphrag index --root ./labor-law` | `legal-skills/03_graphrag_pipeline.md` | ☐ |
| 3.6 | Kiểm tra output: entities.parquet, relationships.parquet, communities.parquet | `legal-skills/03_graphrag_pipeline.md` | ☐ |
| 3.7 | Mô hình hóa quan hệ dẫn chiếu chéo giữa BLLĐ và Nghị định hướng dẫn | `legal-skills/03_graphrag_pipeline.md` | ☐ |

---

## Phần 4 — Multi-hop Reasoning & Suy luận trên đồ thị

| # | Hạng mục | File hướng dẫn | Trạng thái |
|---|----------|---------------|-----------|
| 4.1 | Triển khai Global Search cho câu hỏi tổng quát (VD: "quyền lợi của NLĐ khi bị sa thải") | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 4.2 | Triển khai Local Search cho câu hỏi cụ thể về một Điều/Khoản | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 4.3 | Xây dựng multi-hop query: truy vết chuỗi `hành vi → nghĩa vụ → chế tài` (VD: không đóng BHXH → vi phạm Điều nào → phạt bao nhiêu) | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 4.4 | Lọc theo temporal: chỉ trả kết quả từ văn bản còn hiệu lực | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 4.5 | Hiển thị reasoning path và trích dẫn Điều/Khoản cụ thể trong câu trả lời | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 4.6 | Rule-based layer: mã hóa các quy tắc cứng (VD: lương tối thiểu, giờ làm tối đa) để xác thực kết quả LLM | `legal-skills/04_reasoning_retrieval.md` | ✅ |

---

## Phần 5 — Đánh giá & Kiểm thử

| # | Hạng mục | File hướng dẫn | Trạng thái |
|---|----------|---------------|-----------|
| 5.1 | Xây dựng bộ test cases 50+ câu hỏi luật lao động có ground truth | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 5.2 | Đo Precision/Recall trên tập test, so sánh GraphRAG vs RAG thuần vector | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 5.3 | Kiểm tra multi-hop accuracy: câu hỏi yêu cầu ≥ 2 Điều liên kết | `legal-skills/04_reasoning_retrieval.md` | ✅ |
| 5.4 | Kiểm tra citation accuracy: câu trả lời có trích đúng số Điều/Khoản không | `legal-skills/04_reasoning_retrieval.md` | ✅ |

---

## Ghi chú

- **NLĐ** = Người lao động · **NSDLĐ** = Người sử dụng lao động
- Ưu tiên thực hiện theo thứ tự: Phần 1 → 2 → 3 → 4 → 5
- Xem chi tiết hướng dẫn kỹ thuật tại thư mục `legal-skills/`

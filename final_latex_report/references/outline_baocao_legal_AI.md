# OUTLINE BÁO CÁO CHI TIẾT
## Hệ thống Hỏi Đáp Luật Lao Động Việt Nam sử dụng GraphRAG

> **Source code:** https://github.com/trongnd106/legal-AI  
> **Nền tảng:** Microsoft GraphRAG (fork + tùy chỉnh cho domain **luật lao động** Việt Nam)  
> **Corpus triển khai:** Bộ luật Lao động 2019 (45/2019/QH14) và các Nghị định/Thông tư hướng dẫn trong `data/txt/`  
> **Ngôn ngữ:** Python (core GraphRAG + pipeline), TypeScript/Next.js (frontend)

---

## CHƯƠNG 1. GIỚI THIỆU ĐỀ TÀI (~5–6 trang)

### 1.1 Đặt vấn đề

- **Bối cảnh:** Quan hệ lao động tại Việt Nam được điều chỉnh bởi Bộ luật Lao động 2019 cùng hệ thống văn bản hướng dẫn (Nghị định, Thông tư) — cấu trúc phân cấp Phần → Chương → Mục → Điều → Khoản → Điểm, nhiều dẫn chiếu chéo (BLLĐ ↔ NĐ xử phạt ↔ NĐ điều kiện lao động)
- **Thách thức với NLP truyền thống:** Tra cứu theo từ khóa bỏ sót quan hệ ngữ nghĩa; câu hỏi lao động thường cần nối nhiều Điều (quyền/nghĩa vụ → chế tài → mức phạt hành chính)
- **Hạn chế của Naive RAG thuần túy:** Chỉ tìm theo vector cục bộ; khó trả lời câu hỏi tổng hợp (VD: toàn bộ quyền NLĐ khi chấm dứt HĐLĐ) hoặc chuỗi suy luận BLLĐ → NĐ 12/2022
- **Hạn chế của LLM thuần túy:** Hallucination, không trích dẫn đúng số Điều/Khoản, lẫn lộn với lĩnh vực pháp luật khác (dân sự, hình sự)
- **Nhu cầu thực tế:** Trợ lý hỏi đáp và phân tích hợp đồng lao động (HĐLĐ) có trích dẫn nguồn, hỗ trợ NLĐ/NSDLĐ tra cứu quyền lợi, nghĩa vụ, thủ tục

### 1.2 Khảo sát các giải pháp hiện có và hạn chế

- **Naive RAG (LangChain / LlamaIndex):** Phù hợp tra cứu một Điều; kém khi cần tổng hợp nhiều chương (HĐLĐ, tiền lương, BHXH) hoặc liên kết BLLĐ với Nghị định hướng dẫn
- **BM25 / Elasticsearch:** Mạnh keyword; yếu ngữ nghĩa và thực thể domain (`HopDongLaoDong`, `CheTai`, `XuLyKyLuat`)
- **Chatbot tổng quát (ChatGPT, Gemini):** Không gắn corpus nội bộ đã index; rủi ro trích sai Điều hoặc dùng quy định đã hết hiệu lực
- **Knowledge Graph thủ công (Neo4j + ontology tay):** Tốn công với ~581 Điều BLLĐ; khó đồng bộ khi văn bản sửa đổi
- **Hạn chế chung:** Thiếu kết hợp retrieval cục bộ (một Điều/Khoản) và suy luận toàn corpus (community reports); cần ontology lao động, không dùng schema pháp luật chung chung

### 1.3 Mục tiêu, đối tượng và phạm vi nghiên cứu

- **Mục tiêu:** Xây dựng **Trợ lý Ảo Luật Lao Động Việt Nam** trên GraphRAG — đồ thị tri thức hai lớp (cấu trúc văn bản + ngữ nghĩa lao động) kết hợp Local/Global Search và lớp kiểm chứng quy tắc
- **Đối tượng:** Văn bản **luật lao động** đã thu thập dạng `.txt` trong `data/txt/` (BLLĐ 2019, NĐ 145/2020, NĐ 12/2022, NĐ 74/2024, NĐ 70/2023, TT 10/2020, VBHN BHXH)
- **Phạm vi đã triển khai:**
  - Pipeline chuẩn bị dữ liệu: `scripts/01_prepare_data.py` → JSONL theo Điều; `scripts/02_merge_structural_graph.py` → graph cấu trúc (Lớp 1)
  - Indexing GraphRAG: `graphrag index --root data/labor-law` — trích xuất thực thể ngữ nghĩa (Lớp 2), community reports
  - Query: module `query/` (`local_search`, `global_search`, `multihop_reasoning`, `temporal_filter`, `rule_validator`)
  - Giao diện: `api/` (FastAPI) + `frontend/` (Next.js); demo bổ sung `unified-search-app/` (phân tích HĐLĐ)
  - Đánh giá: `tests/evaluation_suite.py` (keyword/citation accuracy); tùy chọn `scripts/ragas_graphrag_benchmark.py` (RAGAS)
- **Ngoài phạm vi corpus hiện tại:** Bản án, luật dân sự/hình sự/doanh nghiệp (chỉ có test case mẫu trong evaluation, chưa index riêng)

### 1.4 Định hướng giải pháp và đóng góp

- **Đóng góp 1:** Ontology **luật lao động** hai lớp — Lớp 1 (`VanBan`, `Chuong`, `Dieu`, `Khoan`, `Diem`) deterministic; Lớp 2 (`ChuThe`, `HanhVi`, `HopDongLaoDong`, `TienLuong`, …) qua LLM (`data/labor-law/settings.yaml`, `legal-skills/02_ontology_design.md`)
- **Đóng góp 2:** Chunking theo Điều (`chunking.size=4000`, `overlap=0`) — không cắt giữa Khoản; metadata `norm_type` (quyen/nghia_vu/cam_doan/thu_tuc)
- **Đóng góp 3:** Prompt tùy chỉnh tiếng Việt: `prompts/extract_graph_simple.txt`, `prompts/community_report_labor.txt`
- **Đóng góp 4:** Lớp truy vấn và kiểm chứng: multi-hop trên merged graph, lọc hiệu lực văn bản, `rule_validator` cho quy tắc cứng lao động
- **Đóng góp 5:** Ứng dụng thực tế: chat hỏi đáp (`/api/chat`) + phân tích vi phạm HĐLĐ (`unified-search-app/app/contract_analysis/`, rules VR001–VR016)
- **Đóng góp 6:** Bộ benchmark `tests/evaluation_suite.py` — ưu tiên domain `lao_dong`, có thêm case `cross_domain` / domain khác để mở rộng sau

### 1.5 Bố cục báo cáo

- **Chương 1:** Giới thiệu đề tài, vấn đề, mục tiêu (phạm vi luật lao động)
- **Chương 2:** Cơ sở lý thuyết — LLM, RAG, Knowledge Graph, GraphRAG
- **Chương 3:** Phân tích và thiết kế hệ thống — pipeline indexing/querying, ontology lao động
- **Chương 4:** Thực nghiệm và đánh giá — benchmark keyword/citation, so sánh search modes
- **Chương 5:** Tổng kết và hướng phát triển
- **Phụ lục:** Prompt, `settings.yaml`, cấu trúc repo, case study lao động

---

## CHƯƠNG 2. CƠ SỞ LÝ THUYẾT VÀ CÔNG NGHỆ (~10–12 trang)

### 2.1 Mô hình ngôn ngữ lớn (LLM)

#### 2.1.1 Tổng quan LLM
- Định nghĩa, kiến trúc Transformer, cơ chế Self-Attention và Feed-Forward Network
- Ưu điểm: hiểu ngữ nghĩa sâu, suy luận, tóm tắt, sinh văn bản tự nhiên
- Hạn chế: hallucination, knowledge cutoff, context window giới hạn, chi phí inference

#### 2.1.2 Các mô hình đang sử dụng trong hệ thống
- **Completion (indexing + QA):** LiteLLM qua Kilo gateway — `kilo-auto/free` trong `data/labor-law/settings.yaml` (`GRAPHRAG_API_KEY`, `api_base: https://api.kilo.ai/api/gateway`); có cấu hình thay thế `gpt-4o-mini` trong `settings copy.yaml`
- **Embedding:** Ollama local — `qwen3-embedding:4b` (`http://localhost:11434`); `vector_size: 2560` phải khớp dim embedding
- Kiểm tra model: `scripts/test_llm_models.py`
- Bảng so sánh: chi phí gateway vs OpenAI, hỗ trợ tiếng Việt, độ ổn định extraction

#### 2.1.3 Thách thức xử lý tiếng Việt trong domain luật lao động
- Thuật ngữ: NLĐ, NSDLĐ, HĐLĐ, BHXH, BHTN, thử việc, trợ cấp thôi việc, kỷ luật lao động
- Phân biệt thực thể: `CheTai` (xử phạt hành chính — NĐ 12/2022) vs `XuLyKyLuat` (kỷ luật nội bộ — BLLĐ)
- Viết tắt văn bản: BLLĐ, NĐ-CP, TT-BLĐTBXH; canonical id `BLLĐ_2019_Điều_35` vs chuỗi "Điều 35" từ LLM

### 2.2 Retrieval-Augmented Generation (RAG)

#### 2.2.1 Naive RAG — Khái niệm và nguyên lý
- Pipeline: Indexing (chunking → embedding) → Retrieval (cosine similarity) → Generation
- Trong GraphRAG: **Basic Search** tương đương naive RAG trên text units
- Hạn chế với câu hỏi lao động đa Điều (VD: không trả lương → Điều nào → phạt bao nhiêu theo NĐ 12/2022)

#### 2.2.2 Từ Naive RAG đến GraphRAG
- Câu hỏi cục bộ: "Điều 35 BLLĐ — NLĐ đơn phương chấm dứt HĐLĐ trong trường hợp nào?" → Local Search
- Câu hỏi tổng hợp: "Quyền cơ bản của người lao động?" → Global Search + `domain_filter=lao_dong`
- Sơ đồ so sánh: Basic/Naive RAG vs Local vs Global trên cùng corpus `data/labor-law`

### 2.3 Knowledge Graph và Graph-based Reasoning

#### 2.3.1 Knowledge Graph trong luật lao động
- **Lớp 1 (cấu trúc):** `VanBan` → `Chuong` → `Dieu` → `Khoan` → `Diem`; quan hệ `contains`, `cites`, `issued_by`, `guided_by`
- **Lớp 2 (ngữ nghĩa):** `ChuThe`, `HanhVi`, `CoQuan`, `HopDongLaoDong`, `TienLuong`, `NghiPhep`, `CheDoBaoHiem`, …
- Quan hệ ngữ nghĩa (trong prompt): `obligates`, `entitles`, `prohibits`, `regulates`, `penalizes`, `enforced_by`
- Community Detection (Leiden) → community reports phục vụ Global Search

#### 2.3.2 Graph-augmented Retrieval
- Merge graph: `scripts/02_merge_structural_graph.py` + output GraphRAG
- `query/multihop_reasoning.py`: truy vết chuỗi trên merged graph
- Community summary: `community_report_labor.txt` — tóm tắt cụm thực thể lao động

### 2.4 Kiến trúc GraphRAG (Microsoft)

#### 2.4.1 Tổng quan GraphRAG pipeline
- Nguồn gốc: Microsoft Research — GraphRAG paper/blog
- Hai giai đoạn: Indexing (offline) và Querying (online)
- Cấu trúc repo: `packages/graphrag/`, `query/`, `api/`, `frontend/`, `data/labor-law/`, `scripts/`, `legal-skills/`

#### 2.4.2 Indexing Pipeline (triển khai `data/labor-law`)
- Input JSONL: mỗi record = 1 Điều (`id`, `van_ban`, `so_dieu`, `tieu_de`, `norm_type`, `noi_dung`, `khoans[]`)
- Chunking: 1 Điều ≈ 1 chunk (`size=4000`, `overlap=0`)
- LLM extract graph: `extract_graph_simple.txt`, `max_gleanings: 1`
- Community reports: `community_report_labor.txt`
- Output: `data/labor-law/output/` (parquet), `cache/`, vector store theo cấu hình GraphRAG

#### 2.4.3 Query Modes
- **Local Search:** Entity + text units — câu hỏi một Điều/Khoản (`query/local_search.py`, `api/routes/chat.py` mode `local`)
- **Global Search:** Map-reduce community reports — câu hỏi tổng quát (`query/global_search.py`, mode `global`)
- **Basic Search:** Baseline vector RAG (so sánh trong tài liệu GraphRAG / benchmark)
- **Multi-hop / temporal / rules:** Lớp bổ sung trong `query/`, không phải mode GraphRAG gốc

### 2.5 Công nghệ và thư viện hỗ trợ
- **Python:** `uv`, `pyproject.toml`; cài `pip install -e packages/graphrag` cho API
- **Vector store:** theo cấu hình GraphRAG (file/parquet + embedding index)
- **Graph artifacts:** parquet (`entities`, `relationships`, `communities`, `text_units`, `community_reports`)
- **API:** FastAPI (`api/main.py`); **Frontend:** Next.js 15 (`frontend/`)
- **Demo HĐLĐ:** Streamlit `unified-search-app/` + `contract_analysis/`
- **Tài liệu kỹ thuật:** `legal-skills/`, `DEVELOPING.md`, `docs/`

---

## CHƯƠNG 3. PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG (~12–14 trang)

### 3.1 Phân tích yêu cầu hệ thống

**Yêu cầu chức năng:**
- Chuẩn hóa văn bản lao động `.txt` → JSONL theo Điều và metadata hiệu lực
- Index GraphRAG và hỏi đáp tiếng Việt có trích dẫn Điều/Khoản
- Local Search (chi tiết Điều) và Global Search (tổng hợp chủ đề lao động)
- Upload/xem văn bản qua API documents (`api/routes/documents.py`)
- Phân tích HĐLĐ: tách khoản, rule-based VR001–VR016, đối chiếu graph (`contract_analysis/`)

**Yêu cầu phi chức năng:**
- Indexing offline; query qua API (thời gian phụ thuộc Global map-reduce)
- Cấu hình tập trung `data/labor-law/settings.yaml`, biến môi trường `GRAPHRAG_API_KEY`
- Cache LLM JSON (`data/labor-law/cache/`) — quan trọng khi chạy lại indexing
- Một index chính: `data/labor-law` (mở rộng thêm văn bản qua `data/txt/` + re-index)

### 3.2 Kiến trúc tổng thể hệ thống

- **Sơ đồ kiến trúc tổng thể:**
  ```
  data/txt/*.txt (BLLĐ, NĐ, TT, VBHN BHXH)
      ↓ [01_prepare_data.py — parse Điều/Khoản]
  data/labor-law/chunks/*.jsonl + metadata.json
      ↓ [02_merge_structural_graph.py — Lớp 1 graph]
      ↓ [graphrag index — LLM Lớp 2 + communities]
  data/labor-law/output/ (parquet + embeddings)
      ↓ [query/loader.py → local | global | multihop]
  api/ + frontend/  →  Câu trả lời + trích dẫn
  unified-search-app/  →  Phân tích HĐLĐ (demo)
  ```
- **Thành phần chính:**
  - `packages/graphrag/`: engine GraphRAG (index + query API)
  - `scripts/`: chuẩn bị dữ liệu, merge graph, inspect, benchmark RAGAS
  - `query/`: wrapper truy vấn và reasoning cho corpus lao động
  - `api/` + `frontend/`: sản phẩm hỏi đáp chính
  - `data/labor-law/`: settings, prompts, chunks, output
  - `legal-skills/`: checklist và hướng dẫn triển khai
- **Bảng công nghệ:** Python, FastAPI, Next.js, LiteLLM/Kilo, Ollama embedding, Leiden, Parquet

### 3.3 Thiết kế Pipeline Indexing

#### 3.3.1 Chuẩn bị và tiền xử lý dữ liệu luật lao động
- Nguồn: `data/txt/` (7 file mapped trong `FILE_MAP` của `01_prepare_data.py`)
- Đầu ra: `data/labor-law/normalized/`, `chunks/*.jsonl`, `metadata.json` (ngày ban hành, hiệu lực, `huong_dan_boi`)
- Parse cấu trúc: Phần → Chương → Mục → Điều → Khoản → Điểm; gắn `norm_type` cho từng Điều
- Thống kê tham chiếu (ontology doc): ~581 Điều, ~2069 Khoản (BLLĐ và văn bản đi kèm)

#### 3.3.2 Entity & Relation Extraction (Lớp 2 — LLM)
- Prompt: `data/labor-law/prompts/extract_graph_simple.txt`
- **Không** extract Lớp 1 (`Dieu`, `Khoan`, …) bằng LLM — tránh trùng node
- Entity types trong `settings.yaml`: `ChuThe`, `HanhVi`, `CoQuan`, `HopDongLaoDong`, `TienLuong`, `TraLuong`, `ThoiGioLamViec`, `NghiPhep`, `XuLyKyLuat`, `CheDoBaoHiem`, `TroCapThoiViec`, `CheTai`, `AnToanVeSinhLaoDong`
- Quan hệ: mô tả trong prompt (entitles, obligates, prohibits, regulates, penalizes, …)
- `max_gleanings: 1` — cân bằng độ phủ và chi phí LLM

#### 3.3.3 Knowledge Graph hai lớp và Community Detection
- Lớp 1: merge deterministic (`02_merge_structural_graph.py`)
- Lớp 2: GraphRAG standard indexing
- Community detection + `community_report_labor.txt` (`max_length: 2000`)
- Canonicalization: alias "Điều 35" → `BLLĐ_2019_Điều_35` (thiết kế Lớp 1.5 trong ontology doc)

#### 3.3.4 Embedding và Indexing
- Embedding local Ollama `qwen3-embedding:4b`
- `summarize_descriptions.max_length: 500`
- Kiểm tra output: `scripts/03_inspect_output.py`, `api/services/graph_loader.py`

### 3.4 Thiết kế Pipeline Querying

#### 3.4.1 Local Search
- `query/local_search.py` → GraphRAG `local_search` API
- Phù hợp: tra cứu Điều/Khoản, thời gian thử việc, nghỉ phép, điều kiện đơn phương chấm dứt HĐLĐ
- Ví dụ API: `POST /api/chat` `{ "question", "mode": "local" }`

#### 3.4.2 Global Search
- `query/global_search.py` — map-reduce trên community reports
- Tham số: `community_level`, `domain_filter` (VD: `lao_dong` thêm ngữ cảnh vào query)
- Phù hợp: "Quyền cơ bản của người lao động?", tổng hợp chế độ BHXH

#### 3.4.3 Multi-hop, temporal và rule validator
- `query/multihop_reasoning.py`: chuỗi `hành vi → nghĩa vụ → chế tài` (VD: LD012 — lương tối thiểu → NĐ 12/2022)
- `query/temporal_filter.py`: lọc văn bản `con_hieu_luc` từ `metadata.json`
- `query/rule_validator.py`: xác thực câu trả lời với quy tắc cứng

#### 3.4.4 Giao diện người dùng
- **Frontend + API (chính):** Chat hỏi đáp, quản lý tài liệu (`skills/luat-lao-dong-ai-ui-spec.md`)
- **Unified Search App:** Demo Microsoft + tab **Phân tích hợp đồng lao động** (`contract_analysis/`: segmentation, rules, GraphRAG mapper)
- Health check: `/api/health` → `graphrag_ready` sau khi index xong

### 3.5 Tùy chỉnh Prompt Templates cho Luật Lao Động

- `data/labor-law/prompts/extract_graph_simple.txt` — quy tắc phân loại `HanhVi` vs `CheTai` vs `XuLyKyLuat`
- `data/labor-law/prompts/community_report_labor.txt` — báo cáo cộng đồng theo chủ đề lao động
- Prompt query: dùng system prompt mặc định GraphRAG + ngữ cảnh từ `query/global_search.py` (`DOMAIN_LABELS`)
- Contract analysis: `unified-search-app/app/contract_analysis/prompts.py` (phân tích khoản HĐLĐ, vi phạm)

### 3.6 Thiết kế Bộ Dữ Liệu Đánh Giá

- **Corpus thực nghiệm:** Chỉ văn bản trong `data/txt/` → index tại `data/labor-law` (không phải toàn bộ pháp điển VN)
- **Bộ test:** `tests/evaluation_suite.py` — cấu trúc `{ id, domain, category, difficulty, question, expected_keywords, expected_citations, reasoning_chain? }`
- **Phân loại category (triển khai):**
  - `single_hop`: một Điều/văn bản trả lời trực tiếp
  - `multi_hop`: ≥ 2 Điều hoặc BLLĐ → Nghị định (VD: LD011, LD012)
  - `cross_domain`: câu hỏi giao thoa (design cho tương lai; corpus hiện tại chủ yếu lao động)
- **Domain:** `lao_dong` (trọng tâm, 8+ case LD*), `dan_su`, `hinh_su`, `doanh_nghiep` (case mẫu — **chưa** có index riêng)
- **Metrics:** `keyword_accuracy`, `citation_accuracy` qua `evaluate_system()`; không dùng thang 0–20 LLM-Judge tích hợp sẵn trong repo

---

## CHƯƠNG 4. THỰC NGHIỆM VÀ ĐÁNH GIÁ (~10–12 trang)

### 4.1 Môi trường và Bộ Dữ Liệu Thực Nghiệm

- **Phần cứng:** CPU/RAM; embedding Ollama local (GPU tùy máy); LLM qua API gateway
- **Phần mềm:** Python + `uv`; Node 20 cho frontend; phiên bản từ `pyproject.toml`, `api/requirements.txt`
- **Biến môi trường:** `GRAPHRAG_API_KEY`; Ollama tại `localhost:11434`
- **Corpus đã index:**
  - 7 văn bản lao động/BHXH trong `FILE_MAP`
  - Thống kê sau indexing (điền từ `03_inspect_output.py` / log): số entities Lớp 2, relationships, communities, text units
- **Bộ câu hỏi:** ~24 test case trong `TEST_CASES`; báo cáo theo `domain` và `category`

### 4.2 Phương Pháp Đánh Giá

#### 4.2.1 Đánh giá có ground truth (`evaluation_suite.py`)
- **Keyword accuracy:** Tất cả `expected_keywords` xuất hiện trong câu trả lời (VD: "12 ngày", "Điều 113")
- **Citation accuracy:** `cited_articles` khớp `expected_citations` (VD: Điều 35, Điều 46)
- Phù hợp câu hỏi lao động có đáp án số liệu/Điều cụ thể
- Hàm: `evaluate_system(answer_fn)` — `answer_fn(question, domain) -> {answer, cited_articles}`

#### 4.2.2 Đánh giá bổ sung (tùy chọn — RAGAS)
- Script: `scripts/ragas_graphrag_benchmark.py`
- Metrics RAGAS (Faithfulness, Answer Relevancy) — LLM-as-judge qua cấu hình Ragas/Gemini (xem `my-docs/ragas_graphrag_benchmark_guide.md`)
- **Lưu ý:** Chưa phải pipeline mặc định của dự án; dùng khi cần so sánh định tính câu trả lời mở

### 4.3 Các Kịch Bản Thực Nghiệm

#### 4.3.1 So sánh Local vs Global Search (thí nghiệm chính)
- Cùng bộ câu hỏi `lao_dong` từ `TEST_CASES`
- Kỳ vọng: Local tốt `single_hop`; Global tốt hơn câu hỏi mở rộng nhiều Điều (nếu có case tổng hợp trong bộ test)

#### 4.3.2 So sánh với Basic/Naive RAG
- GraphRAG Basic Search hoặc vector-only baseline (benchmark script / thủ công)
- Mục tiêu: chứng minh graph + community giúp `multi_hop` (LD010–LD012)

#### 4.3.3 Multi-hop và merged graph
- Đo hit rate khi bật `multihop_reasoning` vs chỉ Local Search
- Case: trợ cấp thôi việc + đơn phương chấm dứt (LD011), lương tối thiểu + NĐ 12/2022 (LD012)

#### 4.3.4 Temporal filter
- Case TMP001/TMP002: văn bản còn/hết hiệu lực (`metadata.json`)

#### 4.3.5 Phân tích theo category và domain
- Bảng: `category` × mode → keyword/citation accuracy
- Tách riêng kết quả `lao_dong` vs domain chưa có corpus

#### 4.3.6 Phân tích hợp đồng lao động (ứng dụng)
- Rule-based VR001–VR016 trên text HĐLĐ
- Đối chiếu GraphRAG (`contract_analysis/mapper.py`, `mapper_optimized.py`)
- Metrics: số vi phạm phát hiện, căn cứ Điều BLLĐ trích được

### 4.4 Kết Quả và Phân Tích

- **Bảng kết quả:** keyword_accuracy, citation_accuracy theo mode và category
- **Phân tích theo loại câu hỏi lao động:**
  - `single_hop` (nghỉ phép, thử việc, lương tối thiểu): kỳ vọng Local Search mạnh
  - `multi_hop` (trợ cấp thôi việc, xử phạt NĐ 12/2022): cần graph + multihop
- **Case study (ví dụ trong phụ lục):** thay ví dụ BLDS/người tiêu dùng bằng case BLLĐ thực tế
- **Thảo luận:**
  - Chi phí/thời gian indexing (~581 Điều, nhiều lần gọi LLM, cache quan trọng)
  - Phụ thuộc Kilo gateway + Ollama embedding
  - Hạn chế: test case domain khác chưa có index; Global Search chậm hơn Local

---

## CHƯƠNG 5. TỔNG KẾT VÀ HƯỚNG PHÁT TRIỂN (~3–4 trang)

### 5.1 Kết Quả Đạt Được

- Pipeline end-to-end: `data/txt` → JSONL theo Điều → GraphRAG index → API hỏi đáp lao động
- Ontology hai lớp và prompt domain lao động
- Module `query/` (local, global, multihop, temporal, rules)
- Frontend + API; demo phân tích HĐLĐ

| Đóng góp | Mô tả | Kết quả |
|---|---|---|
| Ontology lao động 2 lớp | L1 deterministic + L2 LLM | Graph nhất quán, không trùng Điều |
| Chunking theo Điều | overlap=0 | Không cắt giữa Khoản |
| Dual search + multihop | Local/Global + merged graph | Phù hợp tra cứu và chuỗi suy luận |
| API + Frontend | Chat + quản lý văn bản | Sản phẩm demo luật lao động |
| Benchmark | `evaluation_suite.py` | Keyword/citation accuracy trên case LD* |
| Phân tích HĐLĐ | contract_analysis + VR rules | Kiểm tra điều khoản HĐLĐ vs BLLĐ |

### 5.2 Hạn Chế

- **Corpus hẹp:** Mới index văn bản lao động/BHXH trong `data/txt/`, chưa phủ BLDS, luật hình sự, doanh nghiệp dù có test mẫu
- **Phụ thuộc dịch vụ:** Kilo gateway cho LLM; Ollama cho embedding — cần môi trường local ổn định
- **Indexing tốn thời gian/chi phí:** Nhiều chunk × LLM extraction; phụ thuộc cache khi chạy lại
- **Global Search:** Latency cao (map-reduce nhiều community reports)
- **Đánh giá:** Chủ yếu keyword/citation rule-based; RAGAS và human expert review chưa làm mặc định
- **Graph tĩnh:** Cập nhật văn bản mới cần chạy lại `01_prepare_data.py` + index

### 5.3 Hướng Phát Triển

- Mở rộng corpus: thêm Nghị định lao động, Thông tư BLĐTBXH; index tách hoặc gộp vào `data/labor-law`
- Embedding tiếng Việt chuyên ngành lao động (fine-tune hoặc model lớn hơn trên Ollama)
- Hoàn thiện canonicalization Lớp 1.5 (alias Điều → id) trong merge graph
- Incremental indexing khi văn bản sửa đổi (NĐ thay thế, VBHN)
- Tích hợp RAGAS/evaluator LLM vào CI cho regression test
- Streaming response, UX cho NLĐ/NSDLĐ; mở rộng OCR HĐLĐ scan (`contract_analysis/ocr_pdf.py`)
- **Không ưu tiên ngay:** bản án lao động, pháp luật chung toàn hệ thống VN — ngoài phạm vi đề tài hiện tại

---

## PHỤ LỤC

### Phụ lục A — Cấu Hình Hệ Thống

- `data/labor-law/settings.yaml`: LLM (Kilo), embedding (Ollama), chunking, `entity_types`, prompts
- Biến môi trường: `GRAPHRAG_API_KEY`
- Lệnh: `python scripts/01_prepare_data.py` → `graphrag index --root data/labor-law` → `python -m api.main` + `cd frontend && npm run dev`

### Phụ lục B — Prompt Templates Tùy Chỉnh

- `extract_graph_simple.txt` — extraction Lớp 2
- `community_report_labor.txt` — community reports
- `contract_analysis/prompts.py` — phân tích HĐLĐ
- So sánh với prompt mặc định Microsoft GraphRAG

### Phụ lục C — Cấu Trúc Thư Mục Dự Án Chi Tiết

```
legal-AI/  (graphrag repo)
├── packages/graphrag/       # Core GraphRAG (fork microsoft/graphrag)
├── query/                   # Loader, local/global search, multihop, temporal, rules
├── api/                     # FastAPI — chat, documents, health
├── frontend/                # Next.js — UI hỏi đáp luật lao động
├── data/
│   ├── txt/                 # Nguồn .txt thô (BLLĐ, NĐ, TT, VBHN)
│   └── labor-law/           # Index chính
│       ├── settings.yaml
│       ├── prompts/
│       ├── chunks/*.jsonl
│       ├── metadata.json
│       ├── output/          # parquet artifacts
│       └── cache/
├── scripts/
│   ├── 01_prepare_data.py
│   ├── 02_merge_structural_graph.py
│   ├── 03_inspect_output.py
│   └── ragas_graphrag_benchmark.py
├── tests/evaluation_suite.py
├── unified-search-app/      # Demo + contract_analysis HĐLĐ
├── legal-skills/            # Checklist & hướng dẫn lao động
├── skills/                  # UI spec, feature docs
├── my-docs/                 # Ghi chú kỹ thuật (RAGAS, flow)
└── pyproject.toml
```

### Phụ lục D — Ví Dụ Case Study Chi Tiết (Luật Lao Động)

**Case Study 1: Tra cứu một Điều — Local Search**

*Câu hỏi:* "Thời gian thử việc tối đa đối với công việc đòi hỏi trình độ chuyên môn là bao lâu?" (LD003)

- Kỳ vọng Local Search: chunk `BLLĐ_2019_Điều_27` + entity `ThoiGioLamViec` / `HanhVi` → "60 ngày", trích Điều 27
- Global Search: có thể tổng quát hóa, thiếu chi tiết số ngày
- Đánh giá: `expected_keywords`: ["60 ngày", "Điều 27"]

**Case Study 2: Multi-hop BLLĐ → Nghị định — Multi-hop / Local + graph**

*Câu hỏi:* "Công ty trả lương dưới mức tối thiểu vùng IV thì bị phạt bao nhiêu?" (LD012)

- Chuỗi: Điều 90 BLLĐ (nghĩa vụ trả lương) → NĐ 12/2022 (mức phạt hành chính)
- `reasoning_chain` trong test case; cần relationship `penalizes` / trích NĐ 12/2022
- Naive RAG: thường chỉ retrieve chunk Điều 90, bỏ sót NĐ xử phạt

**Case Study 3: Đơn phương chấm dứt HĐLĐ và trợ cấp thôi việc**

*Câu hỏi:* "NLĐ đơn phương chấm dứt đúng pháp luật có được trợ cấp thôi việc không và cần điều kiện gì?" (LD011)

- Liên kết Điều 35 (quyền, báo trước) → Điều 46 (trợ cấp thôi việc)
- Local Search + multihop trên merged graph vs chỉ vector similarity
- Phân tích HĐLĐ (ứng dụng): rule VR phạt tiền NLĐ, điều khoản đơn phương chấm dứt trái pháp luật

**Case Study 4: Phân tích hợp đồng lao động (Unified Search / contract_analysis)**

- Input: file HĐLĐ (text/PDF)
- Pipeline: tách khoản → rules VR001–VR016 → đối chiếu GraphRAG entities (`HopDongLaoDong`, `TienLuong`, …)
- Output: báo cáo vi phạm kèm căn cứ Điều BLLĐ (VD: cấm phạt tiền thay kỷ luật — Điều 127)

---

*Báo cáo theo chuẩn đề tài tốt nghiệp Đại học, ước lượng ~45–50 trang chính văn. Phạm vi mô tả khớp triển khai tại `data/labor-law` và các module `query/`, `api/`, `frontend/`.*

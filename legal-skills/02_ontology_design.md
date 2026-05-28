# Skill 02 — Thiết kế Ontology & Cấu hình Entity cho GraphRAG

> **Phủ checklist**: mục 2.1 · 2.2 · 2.3 · 2.4 · 2.5  
> **Repo path**: `data/labor-law/prompts/` + `data/labor-law/settings.yaml`  
> **Phụ thuộc**: Skill 01 (`scripts/01_prepare_data.py`) — cung cấp structural graph

---

## Nguyên tắc thiết kế: 2 lớp graph

Ontology luật lao động gồm **hai lớp độc lập**, không trộn lẫn:

| Lớp | Câu hỏi trả lời | Nguồn dữ liệu | Entity types |
|-----|----------------|---------------|--------------|
| **Lớp 1 — Cấu trúc văn bản** | Quy phạm **nằm ở đâu**? | Skill 01 (rule-based, deterministic) | `VanBan`, `Chuong`, `Dieu`, `Khoan`, `Diem` |
| **Lớp 2 — Ngữ nghĩa pháp lý** | Quy phạm **nói về cái gì / ai**? | GraphRAG LLM extraction | `ChuThe`, `HanhVi`, `CoQuan`, `HopDongLaoDong`… |

**Tại sao tách?**

- Lớp 1 đã có sẵn trong `data/labor-law/chunks/*.jsonl` (581 Điều, 2069 Khoản) — parse chính xác 100%, không cần LLM extract lại.
- Nếu LLM extract lại `Dieu`/`Khoan` từ chunk → tạo node trùng ("Điều 35" xuất hiện 2 lần), graph không nhất quán.
- Lớp 2 cần LLM vì phải **hiểu nội dung** ("NLĐ có quyền…", "không đóng BHXH") — không parse được bằng regex.

```
┌─────────────────────────────────────────────────────────────────┐
│  Lớp 1 — Structural (Skill 01, rule-based)                      │
│                                                                 │
│  VanBan ──contains──> Chuong ──contains──> Dieu ──contains──> Khoan ──contains──> Diem
│     │                                         │
│     ├──issued_by──> CoQuan                    │
│     ├──amends / repeals / guided_by──> VanBan │
│     └──cites──> Dieu (cross-ref)              │
└─────────────────────────────────────────────────────────────────┘
                              │
                    (link qua id: BLLĐ_2019_Điều_35)
                              │
┌─────────────────────────────────────────────────────────────────┐
│  Lớp 2 — Semantic (GraphRAG LLM extraction)                   │
│                                                                 │
│  Dieu ──regulates──> HanhVi / HopDongLaoDong / TienLuong…      │
│       ──applies_to──> ChuThe                                    │
│       ──obligates / entitles / prohibits──> ChuThe / HanhVi    │
│       ──penalizes──> CheTai                                      │
│       ──enforced_by──> CoQuan                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
              Lớp 1.5 — Canonicalization (alias index)
              "Điều 35" / "khoản 1 Điều 35" → BLLĐ_2019_Điều_35
```

> **Lớp 1.5 — Canonicalization**: LLM trả về `"Điều 35"` (string), L1 dùng `BLLĐ_2019_Điều_35` (id).  
> Cần alias index khi merge graph — xem [Bước 6](#bước-6--merge-2-lớp-graph-sau-indexing).

---

## Bước 1 — Entity Types

### 1A. Lớp cấu trúc văn bản (2.1) — **KHÔNG extract bằng LLM**

> Nguồn: `scripts/01_prepare_data.py` → `data/labor-law/chunks/*.jsonl`  
> Mỗi record JSONL = 1 node `Dieu` với metadata phân cấp đầy đủ.

| Entity | Mô tả | Ví dụ | Nguồn |
|--------|-------|-------|-------|
| `VanBan` | Văn bản pháp luật | "45/2019/QH14 — BLLĐ 2019" | `metadata.json` |
| `Chuong` | Chương | "Chương III — Hợp đồng lao động" | field `chuong_so`, `ten_chuong` |
| `Dieu` | Điều luật | "Điều 35 — Quyền đơn phương chấm dứt HĐLĐ" | field `so_dieu`, `tieu_de` |
| `Khoan` | Khoản | "Khoản 1 Điều 35" | field `khoans[]` |
| `Diem` | Điểm | "Điểm a Khoản 1 Điều 35" | field `khoans[].diems[]` |

Schema JSONL (đã có từ Skill 01):

```json
{
  "id": "BLLĐ_2019_Điều_35",
  "van_ban": "45/2019/QH14",
  "so_dieu": 35,
  "tieu_de": "Quyền đơn phương chấm dứt hợp đồng lao động của người lao động",
  "chuong_so": "III",
  "ten_chuong": "HỢP ĐỒNG LAO ĐỘNG",
  "muc_so": "2",
  "ten_muc": "CHẤM DỨT HỢP ĐỒNG LAO ĐỘNG",
  "norm_type": "quyen",
  "khoans": [{"so": 1, "noi_dung": "...", "diems": [...]}]
}
```

### 1B. Lớp ngữ nghĩa pháp lý (2.1 phần semantic) — **Extract bằng LLM**

| Entity | Câu hỏi | Ví dụ | Phân biệt với |
|--------|---------|-------|---------------|
| `ChuThe` | **Ai** là bên trong quan hệ pháp luật? | NLĐ, NSDLĐ, người học nghề | ≠ `CoQuan` (cơ quan nhà nước) |
| `HanhVi` | **Làm gì** (hành vi/sự kiện)? | Chấm dứt HĐLĐ, không trả lương, đình công | ≠ `CheTai` (phạt tiền) · ≠ `XuLyKyLuat` (kỷ luật nội bộ) |
| `CoQuan` | **Cơ quan NN** ban hành / thực thi / giám sát? | Quốc hội, Chính phủ, Bộ LĐTBXH, Thanh tra LĐ | ≠ `ChuThe` (bên quan hệ LĐ) |

> **Chiến lược CoQuan 2 nguồn — cần dedup khi merge:**
> - `CoQuan` **ban hành** → build deterministic từ `metadata.json` → `issued_by` (node L1)
> - `CoQuan` **thực thi** → LLM extract từ nội dung Điều ("Thanh tra lao động", "Chính phủ quy định") (node L2)
> - Hai node cùng tên ("Bộ LĐTBXH") từ hai nguồn → merge theo `title.lower()` khi build graph.

### 1C. Entity đặc thù lao động (2.2) — **Extract bằng LLM**

> Đồng bộ checklist 2.2: `HopDongLaoDong`, `TienLuong`, `TraLuong`, `ThoiGioLamViec`,  
> `NghiPhep`, `XuLyKyLuat`, `CheDoBaoHiem` + bổ sung `CheTai`, `TroCapThoiViec`, `AnToanVeSinhLaoDong`.

#### Tier 1 — Bắt buộc (MVP + test cases LD010/LD011)

| Entity | Chương BLLĐ | Mô tả | Ví dụ |
|--------|-------------|-------|-------|
| `HopDongLaoDong` | III | Loại/điều khoản HĐLĐ | "HĐLĐ xác định thời hạn", "HĐLĐ thử việc" |
| `TienLuong` | VI | Mức/cơ cấu lương | "Lương tối thiểu vùng I — 4.960.000đ" |
| `TraLuong` | VI | Thời hạn, hình thức trả lương | "Trả chậm lương", "Trả lương 2 lần/tháng" |
| `ThoiGioLamViec` | VII | Thời gian làm việc | "Không quá 8 giờ/ngày", "48 giờ/tuần" |
| `NghiPhep` | VII | Chế độ nghỉ | "12 ngày nghỉ phép năm" |
| `XuLyKyLuat` | VIII | Hình thức kỷ luật **nội bộ** | "Sa thải", "Kéo dài thời hạn nâng lương" |
| `CheDoBaoHiem` | XII | BHXH/BHYT/BHTN | "BHXH bắt buộc", "Đóng BHXH" |
| `TroCapThoiViec` | III/VI | Trợ cấp khi chấm dứt HĐLĐ | "Trợ cấp thôi việc", "Bồi thường" |
| `CheTai` | VIII + NĐ 12/2022 | Chế tài **hành chính** (phạt tiền) | "Phạt 10–75 triệu", "Phạt vi phạm BHXH" |
| `AnToanVeSinhLaoDong` | IX | AT-VSLĐ, BHLĐ, môi trường làm việc | "Không cung cấp BHLĐ", "Không khám sức khỏe định kỳ" |

#### Tier 2 — Mở rộng (khi corpus đủ lớn)

| Entity | Chương BLLĐ | Mô tả | Ví dụ |
|--------|-------------|-------|-------|
| `TranhChapLaoDong` | XIV | Tranh chấp, hòa giải, trọng tài | "Tranh chấp lương", "Đình công" |
| `ThoaUocTapThe` | V | Thương lượng tập thể | "Thỏa ước lao động tập thể" |
| `DieuKienLamViec` | IV + NĐ 145 | Điều kiện/môi trường làm việc | "Thiết bị bảo hộ", "Nhiệt độ nơi làm việc" |
| `ThoiHan` | Nhiều chương | Thời hạn/thời hiệu pháp lý | "Báo trước 45 ngày", "Trả lương trước ngày 15" |

#### Không cần entity riêng — dùng `HanhVi` + metadata Chương (L1)

Đào tạo nghề (Ch IV), lao động nữ/vị thành niên (Ch X–XI), công đoàn (Ch XIII), cho thuê lại LĐ.

#### Quy tắc phân ranh entity (tránh trùng lẫn)

| Tình huống | Entity đúng | Entity sai |
|------------|-------------|------------|
| "Không đóng BHXH" | `HanhVi` (vi phạm) + `regulates` ← `CheDoBaoHiem` (domain) | Chỉ gán `CheDoBaoHiem` |
| "Sa thải" | `XuLyKyLuat` (hình thức kỷ luật nội bộ) | `HanhVi` (trừ khi mô tả hành vi dẫn đến sa thải) |
| "Phạt 10 triệu đồng" | `CheTai` (chế tài HC) | `XuLyKyLuat` (không phải kỷ luật nội bộ) |
| "Trợ cấp thôi việc" | `TroCapThoiViec` | `TienLuong` (lương ≠ trợ cấp) |
| "Lương tối thiểu vùng I" | `TienLuong` | `TraLuong` (mức lương ≠ cách trả) |
| "Trả lương chậm quá 15 ngày" | `TraLuong` + `HanhVi` | Chỉ `TienLuong` |
| "Không cung cấp BHLĐ" | `AnToanVeSinhLaoDong` + `HanhVi` | `DieuKienLamViec` (Tier 2, tương đương) |

---

## Bước 2 — Relation Types (2.3)

### Relations lớp cấu trúc (build từ Skill 01 + metadata)

| Relation | Chiều | Ý nghĩa | Nguồn |
|----------|-------|---------|-------|
| `contains` | VanBan→Chuong→Dieu→Khoan→Diem | Phân cấp văn bản | JSONL fields |
| `cites` | Dieu→Dieu, Dieu→VanBan | Dẫn chiếu ("theo quy định tại Điều X") | Regex + LLM |
| `amends` | VanBan→VanBan | Sửa đổi văn bản | `metadata.json` |
| `repeals` | VanBan→VanBan | Bãi bỏ văn bản | `metadata.json` |
| `guided_by` | VanBan→VanBan | NĐ hướng dẫn Luật | `metadata.json` (`huong_dan_cho`) |
| `issued_by` | VanBan→CoQuan | Cơ quan ban hành | `metadata.json` (`co_quan`) |

### Relations lớp ngữ nghĩa (extract bằng LLM)

| Relation | Chiều | Ý nghĩa | Ví dụ |
|----------|-------|---------|-------|
| `regulates` | Dieu→HanhVi / Dieu→HopDongLaoDong / Dieu→TienLuong… | Điều luật điều chỉnh khái niệm/hành vi | Điều 35 → "Đơn phương chấm dứt HĐLĐ" |
| `applies_to` | Dieu→ChuThe | Phạm vi áp dụng — **chỉ dùng** khi Điều không rõ obligates/entitles (VD: Điều 2 — đối tượng áp dụng) | Điều 2 → "Người học nghề" |
| `obligates` | Dieu→ChuThe | Áp nghĩa vụ ("phải", "bắt buộc") | Điều 35 → NLĐ phải báo trước 45 ngày |
| `entitles` | Dieu→ChuThe | Trao quyền ("có quyền", "được") | Điều 35 → NLĐ được đơn phương chấm dứt |
| `prohibits` | Dieu→HanhVi | Cấm hành vi ("không được", "cấm") | Điều 8 → phân biệt đối xử |
| `penalizes` | Dieu→CheTai | Chế tài **hành chính** (phạt tiền, NĐ 12/2022) | NĐ 12/2022 → phạt 10–75 triệu |
| `disciplines` | Dieu→XuLyKyLuat | Kỷ luật lao động **nội bộ** (không phải phạt tiền) | Điều 125 → sa thải, khiển trách |
| `enforced_by` | Dieu→CoQuan | Cơ quan thực thi/giám sát | Điều 12 → Bộ LĐTBXH |

> **Quy tắc chọn relation Dieu→ChuThe:**  
> Ưu tiên `obligates` hoặc `entitles` (cụ thể hơn). Chỉ dùng `applies_to` cho phạm vi áp dụng thuần túy.  
> Không dùng `requires: HanhVi→ChuThe` — chiều ngược, dễ nhầm.

### Ví dụ multi-hop (checklist 4.3)

> **Ký hiệu:** `──rel──>` = chiều edge trong graph.  
> Khi query từ `HanhVi`, engine duyệt ngược (traverse inbound edges) để tìm `Dieu` liên quan.

```
"Không đóng BHXH → vi phạm điều nào → phạt bao nhiêu"

Nodes:
  BLLĐ_2019_Điều_168 (Dieu, L1) ──regulates──> Không đóng BHXH (HanhVi, L2)
  BLLĐ_2019_Điều_168            ──regulates──> CheDoBaoHiem (L2)
  ND_12_2022_Điều_38  (Dieu, L1) ──penalizes──> Phạt 10–75 triệu (CheTai, L2)
  ND_12_2022_Điều_38             ──obligates──> NSDLĐ (ChuThe, L2)
  ND_12_2022_Điều_38             ──enforced_by──> Thanh tra LĐ (CoQuan, L2)

Query path (inbound traversal từ HanhVi):
  "Không đóng BHXH" → [inbound regulates] → Điều 168 BLLĐ
                     → [inbound penalizes] → Điều 38 NĐ 12/2022
                                          → [outbound penalizes] → Phạt 10–75 triệu

"NLĐ đơn phương chấm dứt → có trợ cấp thôi việc không?" (LD011)

Nodes:
  BLLĐ_2019_Điều_35 (Dieu, L1) ──regulates──> Đơn phương chấm dứt HĐLĐ (HanhVi, L2)
  BLLĐ_2019_Điều_35             ──entitles──>  NLĐ (ChuThe, L2)
  BLLĐ_2019_Điều_46 (Dieu, L1) ──regulates──> TroCapThoiViec (L2)
  BLLĐ_2019_Điều_46             ──obligates──> NSDLĐ (ChuThe, L2)

Query path:
  "NLĐ" (ChuThe) → [inbound entitles] → Điều 35
                 → [cross-hop: cites/chained] → Điều 46
                 → [outbound regulates] → TroCapThoiViec
```

---

## Bước 3 — Gắn nhãn loại quy phạm (2.4)

Trường `norm_type` đã được gắn sẵn trong JSONL (Skill 01). Dùng làm filter khi query:

| `norm_type` | Từ khóa nhận dạng | Ý nghĩa pháp lý |
|-------------|-------------------|-----------------|
| `nghia_vu` | phải, có trách nhiệm, bắt buộc | NLĐ/NSDLĐ **phải** làm |
| `quyen` | có quyền, được, được phép | NLĐ/NSDLĐ **được** làm |
| `cam_doan` | không được, cấm, nghiêm cấm | **Không được** làm |
| `thu_tuc` | thủ tục, trình tự, hồ sơ | Quy trình thực hiện |
| `khac` | (không khớp keyword) | Định nghĩa, phạm vi, giải thích từ ngữ |

Thống kê trên BLLĐ 2019: `nghia_vu` 111 · `quyen` 67 · `cam_doan` 5 · `thu_tuc` 8 · `khac` 29.

---

## Bước 4 — Cấu hình GraphRAG `settings.yaml` (2.5)

> **Quan trọng:** `entity_types` chỉ liệt kê entity **lớp 2** (semantic + domain).  
> Entity lớp 1 (VanBan, Dieu, Khoan…) **không** đưa vào LLM extraction.

```yaml
# data/labor-law/settings.yaml

llm:
  api_key: ${GRAPHRAG_API_KEY}
  type: openai_chat
  model: gpt-4o-mini          # mini đủ cho extraction, tiết kiệm chi phí
  max_tokens: 4000
  temperature: 0
  request_timeout: 180.0

parallelization:
  stagger: 0.3
  num_threads: 4

input:
  type: file
  file_type: json
  base_dir: "chunks"
  file_pattern: ".*\\.jsonl$"
  document_attribute_columns:
    - id
    - van_ban
    - so_dieu
    - tieu_de
    - chuong_so
    - ten_chuong
    - muc_so
    - norm_type

chunks:
  # size lớn để 1 Điều (trung bình ~800 tokens) không bị cắt.
  # Điều dài nhất (Điều 3 — Giải thích từ ngữ) ~3000 tokens → vẫn nằm trong 1 chunk.
  # overlap: 0 vì mỗi Điều là unit pháp lý độc lập — không cần context từ Điều kề bên.
  # group_by_columns: [id] đảm bảo không bao giờ cắt qua Khoản của cùng một Điều.
  size: 4000
  overlap: 0
  group_by_columns:
    - id               # Mỗi Điều = 1 text unit, không cắt qua Khoản

entity_extraction:
  prompt: "prompts/entity_extraction_labor.txt"
  entity_types:
    # Lớp 2A — Ngữ nghĩa pháp lý
    - ChuThe
    - HanhVi
    - CoQuan
    # Lớp 2B — Domain lao động (Tier 1)
    - HopDongLaoDong
    - TienLuong
    - TraLuong
    - ThoiGioLamViec
    - NghiPhep
    - XuLyKyLuat
    - CheDoBaoHiem
    - TroCapThoiViec
    - CheTai
    - AnToanVeSinhLaoDong
    # Tier 2 — bật khi mở rộng corpus
    # - TranhChapLaoDong
    # - ThoaUocTapThe
    # - DieuKienLamViec
    # - ThoiHan
  max_gleanings: 2

relationship_extraction:
  prompt: "prompts/relationship_extraction_labor.txt"

community_reports:
  prompt: "prompts/community_report_labor.txt"
  max_length: 2000
  max_input_length: 8000

embeddings:
  llm:
    model: text-embedding-3-small
```

---

## Bước 5 — Prompt entity extraction tiếng Việt

Tạo file `data/labor-law/prompts/entity_extraction_labor.txt`:

```
-Goal-
Cho đoạn văn bản thuộc Bộ luật Lao động Việt Nam hoặc các Nghị định hướng dẫn,
hãy trích xuất entity NGỮ NGHĨA và mối quan hệ pháp lý.

-Ngữ cảnh chunk-
Mỗi đoạn văn bản tương ứng với 1 Điều luật, có metadata:
  chunk_id  = {id}        (VD: BLLĐ_2019_Điều_35)
  van_ban   = {van_ban}   (VD: 45/2019/QH14)
  so_dieu   = {so_dieu}   (VD: 35)

LƯU Ý QUAN TRỌNG:
- KHÔNG tạo entity cho VanBan, Chuong, Dieu, Khoan, Diem — chúng đã có trong metadata.
- Khi tạo relationship, dùng {chunk_id} làm source nếu Điều luật này là chủ thể.
  Ví dụ: source="BLLĐ_2019_Điều_35", KHÔNG phải source="Điều 35".
- Khi dẫn chiếu Điều khác ("theo quy định tại Điều X"), dùng relation `cites`
  với target="Điều X" (alias sẽ được resolve tự động khi merge graph).

-Entity Types-
ChuThe, HanhVi, CoQuan
HopDongLaoDong, TienLuong, TraLuong, ThoiGioLamViec, NghiPhep
XuLyKyLuat, CheDoBaoHiem, TroCapThoiViec, CheTai, AnToanVeSinhLaoDong

-Quy tắc phân loại-
HanhVi         = hành vi/sự kiện (không trả lương, đình công, không đóng BHXH)
XuLyKyLuat     = hình thức kỷ luật NỘI BỘ (sa thải, khiển trách) — KHÔNG phải phạt tiền
CheTai         = chế tài HÀNH CHÍNH, phạt tiền (NĐ 12/2022) — KHÔNG phải kỷ luật nội bộ
TienLuong      = mức/cơ cấu lương | TraLuong = thời hạn/hình thức trả lương
TroCapThoiViec = trợ cấp/bồi thường khi chấm dứt HĐLĐ — KHÔNG phải lương định kỳ
applies_to     = chỉ dùng cho phạm vi áp dụng thuần túy (Điều 2); ưu tiên obligates/entitles

-Relationship Types-
regulates, applies_to, obligates, entitles, prohibits, penalizes, disciplines, enforced_by, cites

-Ví dụ-
Chunk metadata: chunk_id=BLLĐ_2019_Điều_35, van_ban=45/2019/QH14, so_dieu=35
Văn bản: "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải
báo trước cho người sử dụng lao động ít nhất 45 ngày nếu làm việc theo hợp đồng lao
động không xác định thời hạn."

Entities:
("entity"<|>"Người lao động"<|>"ChuThe"<|>"Chủ thể có quyền đơn phương chấm dứt HĐLĐ")
("entity"<|>"Người sử dụng lao động"<|>"ChuThe"<|>"Bên nhận thông báo chấm dứt HĐLĐ")
("entity"<|>"Đơn phương chấm dứt HĐLĐ"<|>"HanhVi"<|>"Hành vi chấm dứt hợp đồng một bên")
("entity"<|>"HĐLĐ không xác định thời hạn"<|>"HopDongLaoDong"<|>"Loại hợp đồng vô thời hạn")

Relations:
("relationship"<|>"BLLĐ_2019_Điều_35"<|>"Người lao động"<|>"entitles"<|>"Trao quyền đơn phương chấm dứt HĐLĐ"<|>9)
("relationship"<|>"BLLĐ_2019_Điều_35"<|>"Người lao động"<|>"obligates"<|>"Phải báo trước ít nhất 45 ngày"<|>9)
("relationship"<|>"BLLĐ_2019_Điều_35"<|>"Đơn phương chấm dứt HĐLĐ"<|>"regulates"<|>"Điều luật điều chỉnh hành vi chấm dứt HĐLĐ"<|>8)
("relationship"<|>"BLLĐ_2019_Điều_35"<|>"HĐLĐ không xác định thời hạn"<|>"regulates"<|>"Áp dụng cho loại HĐLĐ vô thời hạn"<|>7)
```

Prompt relationship extraction (`prompts/relationship_extraction_labor.txt`):

```
Chú ý các loại quan hệ đặc thù pháp luật lao động:
- regulates:    Điều luật điều chỉnh hành vi/khái niệm ("quy định về", "điều chỉnh")
- applies_to:   Phạm vi áp dụng thuần túy ("đối tượng áp dụng"); KHÔNG dùng thay obligates/entitles
- obligates:    Áp nghĩa vụ ("phải", "có trách nhiệm", "bắt buộc")
- entitles:     Trao quyền ("có quyền", "được phép")
- prohibits:    Cấm hành vi ("không được", "cấm", "nghiêm cấm")
- penalizes:    Chế tài HÀNH CHÍNH, target phải là CheTai ("bị phạt tiền", "xử phạt vi phạm hành chính")
- disciplines:  Kỷ luật lao động NỘI BỘ, target phải là XuLyKyLuat ("sa thải", "khiển trách", "hạ lương")
- enforced_by:  Cơ quan thực thi ("Bộ LĐTBXH", "Thanh tra lao động", "Chính phủ quy định chi tiết")
- cites:        Dẫn chiếu Điều khác ("theo quy định tại Điều X", "căn cứ Nghị định Y")
                → target = string "Điều X" hoặc "Nghị định Y" (alias sẽ resolve khi merge)
```

---

## Bước 6 — Merge 2 lớp graph sau indexing

Sau khi GraphRAG index xong, cần script merge structural nodes từ JSONL vào graph,
kèm **alias index** để link relation LLM (`"Điều 35"`) → node L1 (`BLLĐ_2019_Điều_35`).

```python
# scripts/02_merge_structural_graph.py  (tạo ở Skill 03)
"""
1. Đọc JSONL → tạo entities/relationships structural (L1)
2. Build alias index context-aware theo van_ban_id để tránh collision
   VD: "Điều 35" trong chunk thuộc BLLĐ_2019 → BLLĐ_2019_Điều_35
       "Điều 35" trong chunk thuộc ND_145_2020 → ND_145_2020_Điều_35
3. Rewrite LLM relationship source/target qua alias index + chunk context
4. Dedup CoQuan nodes theo title.lower() (L1 metadata + L2 LLM có thể trùng)
5. Merge vào output/entities.parquet + relationships.parquet
"""
import json, re
import pandas as pd
from pathlib import Path

CHUNKS = Path("data/labor-law/chunks")
entities, rels = [], []

# alias_index: (so_dieu, van_ban_id) → dieu_id  — dùng tuple key, không bị collision
alias_index: dict[tuple[int, str], str] = {}
# van_ban_slug_map: van_ban_id → slug  — để resolve "Điều 35 BLLĐ"
van_ban_slug: dict[str, str] = {}

for jsonl in CHUNKS.glob("*.jsonl"):
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        dieu_id  = r["id"]
        so       = r["so_dieu"]
        van_ban  = r["van_ban"]

        alias_index[(so, van_ban)] = dieu_id
        van_ban_slug[van_ban] = jsonl.stem  # "45/2019/QH14" → "BLLĐ_2019"

        entities.append({
            "id": dieu_id,
            "title": f"Điều {so}. {r['tieu_de']}",
            "type": "Dieu",
            "description": r["noi_dung"][:500],
            "norm_type": r["norm_type"],
            "van_ban": van_ban,
            "chuong_so": r.get("chuong_so"),
        })
        for k in r.get("khoans", []):
            kid = f"{dieu_id}_Khoản_{k['so']}"
            entities.append({
                "id": kid,
                "title": f"Khoản {k['so']} Điều {so}",
                "type": "Khoan",
                "description": k["noi_dung"][:300],
                "van_ban": van_ban,
            })
            rels.append({
                "source": dieu_id, "target": kid,
                "description": "contains", "weight": 10.0,
            })

def resolve_alias(name: str, chunk_van_ban: str) -> str:
    """
    Map tên LLM → id L1, sử dụng van_ban của chunk làm ngữ cảnh mặc định.

    Ưu tiên:
      1. "Điều 35 45/2019/QH14" hoặc "Điều 35 BLLĐ 2019" → lookup chính xác
      2. "Điều 35" không có văn bản → dùng chunk_van_ban làm fallback
      3. Không resolve được → giữ nguyên string
    """
    name = name.strip()
    m = re.match(r"[Đđ]iều\s+(\d+)", name, re.IGNORECASE)
    if not m:
        return name

    so = int(m.group(1))
    rest = name[m.end():].strip()  # phần sau số điều

    # Tìm van_ban xuất hiện trong phần còn lại của string
    for vid in alias_index:
        _, vb = vid
        if vb in rest or van_ban_slug.get(vb, "") in rest:
            key = (so, vb)
            if key in alias_index:
                return alias_index[key]

    # Fallback: dùng van_ban của chunk đang xử lý
    key = (so, chunk_van_ban)
    return alias_index.get(key, name)

def dedup_coquan(entities: list[dict]) -> list[dict]:
    """Merge CoQuan nodes có cùng title (L1 metadata + L2 LLM extract)."""
    seen: dict[str, dict] = {}
    result = []
    for e in entities:
        if e["type"] != "CoQuan":
            result.append(e)
            continue
        key = e["title"].lower().strip()
        if key not in seen:
            seen[key] = e
            result.append(e)
        # else: node L2 bị bỏ, giữ node L1 (đã append trước)
    return result

# Sau khi load LLM relationships (DataFrame):
# for _, row in llm_rels.iterrows():
#     row["source"] = resolve_alias(row["source"], chunk_van_ban=row["van_ban"])
#     row["target"] = resolve_alias(row["target"], chunk_van_ban=row["van_ban"])

print(f"L1: {len(entities)} entities, {len(rels)} rels")
print(f"Alias index: {len(alias_index)} (Dieu,van_ban) tuples — không collision")
```

---

## Kiểm tra hoàn thành

```bash
# 1. Structural graph đã sẵn sàng (Skill 01)
python3 scripts/01_prepare_data.py --verify

# 2. Validate settings.yaml
graphrag init --root data/labor-law --force
python3 -c "
import yaml
cfg = yaml.safe_load(open('data/labor-law/settings.yaml'))
types = cfg['entity_extraction']['entity_types']
assert 'Dieu' not in types, 'Dieu không được trong LLM entity_types'
assert 'Dieu' not in types, 'Dieu không được trong LLM entity_types'
assert 'ChuThe' in types and 'TraLuong' in types and 'CheTai' in types
assert 'disciplines' not in types, 'disciplines là relation, không phải entity'
print('✅ Entity types (lớp 2, Tier 1):', types)
print(f'   Tổng: {len(types)} types (≤15 khuyến nghị)')
"

# 3. Kiểm tra metadata → issued_by / guided_by relations
python3 -c "
import json
meta = json.load(open('data/labor-law/metadata.json'))
for vid, m in meta.items():
    print(f'{vid}: co_quan={m[\"co_quan\"]}, huong_dan_cho={m.get(\"huong_dan_cho\",\"-\")}')
"
```

**Kết quả mong đợi:**
- Lớp 1: 581 Điều + 2069 Khoản từ JSONL (deterministic)
- Lớp 1.5: alias index `(so_dieu, van_ban)` — không collision giữa 7 văn bản
- Lớp 2: LLM extract 13 entity types Tier 1 (3 semantic + 10 domain)
- Relations: `penalizes` → `CheTai` (HC) · `disciplines` → `XuLyKyLuat` (nội bộ)
- `CoQuan` dedup: node L1 (metadata) và L2 (LLM) cùng tên được merge thành 1

# Skill 02 — Thiết kế Ontology & Cấu hình Entity cho GraphRAG

> **Phủ checklist**: mục 2.1 · 2.2 · 2.3 · 2.4 · 2.5  
> **Repo path**: `data/labor-law/prompts/` + `data/labor-law/settings.yaml`

---

## Tổng quan Ontology Luật Lao động

```
VanBan ──contains──> Chuong ──contains──> Dieu ──contains──> Khoan ──contains──> Diem
   │                                        │
   └──amends / repeals──> VanBan            └──obligates / prohibits / entitles──> HanhVi
                                            └──requires──> ChuThe
```

---

## Bước 1 — Định nghĩa Entity Types (2.1 + 2.2)

### Core structural entities (2.1)
| Entity | Mô tả | Ví dụ |
|--------|-------|-------|
| `VanBan` | Văn bản pháp luật | "Bộ luật Lao động 2019" |
| `Chuong` | Chương trong văn bản | "Chương III - Hợp đồng lao động" |
| `Dieu` | Điều luật | "Điều 35 - Quyền đơn phương chấm dứt HĐLĐ" |
| `Khoan` | Khoản trong điều | "Khoản 1 Điều 35" |
| `Diem` | Điểm trong khoản | "Điểm a Khoản 1 Điều 35" |
| `CoQuan` | Cơ quan ban hành / thực thi | "Bộ Lao động - TB&XH" |
| `ChuThe` | Chủ thể pháp lý | "Người lao động", "Người sử dụng lao động" |
| `HanhVi` | Hành vi được điều chỉnh | "Chấm dứt hợp đồng lao động" |

### Semantic entities đặc thù lao động (2.2)
| Entity | Mô tả | Ví dụ |
|--------|-------|-------|
| `HopDongLaoDong` | Loại/điều khoản HĐLĐ | "HĐLĐ xác định thời hạn" |
| `TienLuong` | Quy định về lương | "Mức lương tối thiểu vùng I" |
| `ThoiGioLamViec` | Thời gian làm việc/nghỉ ngơi | "Không quá 8 giờ/ngày" |
| `NghiPhep` | Chế độ nghỉ | "12 ngày nghỉ phép năm" |
| `XuLyKyLuat` | Hình thức kỷ luật lao động | "Sa thải", "Kéo dài nâng lương" |
| `CheDoBaoHiem` | Bảo hiểm xã hội/y tế/thất nghiệp | "BHXH bắt buộc" |

---

## Bước 2 — Định nghĩa Relation Types (2.3)

| Relation | Chiều | Ý nghĩa |
|----------|-------|---------|
| `contains` | VanBan→Chuong, Chuong→Dieu, Dieu→Khoan | Cấu trúc phân cấp |
| `cites` | Dieu→Dieu hoặc Dieu→VanBan | Dẫn chiếu đến điều/văn bản khác |
| `amends` | VanBan→VanBan | Văn bản này sửa đổi văn bản kia |
| `repeals` | VanBan→VanBan | Văn bản này bãi bỏ văn bản kia |
| `requires` | HanhVi→ChuThe | Yêu cầu chủ thể phải thực hiện |
| `prohibits` | Dieu→HanhVi | Cấm hành vi này |
| `entitles` | Dieu→ChuThe | Trao quyền cho chủ thể |
| `obligates` | Dieu→ChuThe | Áp đặt nghĩa vụ lên chủ thể |
| `penalizes` | Dieu→HanhVi | Chế tài cho hành vi vi phạm |
| `guided_by` | VanBan→VanBan | Nghị định hướng dẫn Luật |

---

## Bước 3 — Gắn nhãn loại quy phạm (2.4)

Thêm trường `norm_type` vào mỗi entity `Dieu` / `Khoan`:

```python
NORM_TYPES = {
    "nghia_vu": [
        "phải", "có trách nhiệm", "có nghĩa vụ", "bắt buộc"
    ],
    "quyen": [
        "có quyền", "được", "được phép"
    ],
    "cam_doan": [
        "không được", "cấm", "nghiêm cấm", "bị cấm"
    ],
    "thu_tuc": [
        "thủ tục", "trình tự", "hồ sơ", "quy trình"
    ]
}

def classify_norm(text: str) -> str:
    for norm_type, keywords in NORM_TYPES.items():
        if any(kw in text.lower() for kw in keywords):
            return norm_type
    return "khac"
```

---

## Bước 4 — Cấu hình GraphRAG `settings.yaml` (2.5)

Chỉnh sửa file `data/labor-law/settings.yaml` (tạo bằng `graphrag init`):

```yaml
# data/labor-law/settings.yaml

input:
  type: file
  file_type: json
  base_dir: "chunks"
  file_pattern: ".*\\.jsonl$"
  document_attribute_columns:
    - van_ban
    - so_dieu
    - tieu_de

chunks:
  size: 800           # ~1 Khoản = ~300-800 từ
  overlap: 100
  group_by_columns:
    - van_ban         # Không cắt qua ranh giới văn bản

entity_extraction:
  prompt: "prompts/entity_extraction_labor.txt"
  entity_types:
    - VanBan
    - Chuong
    - Dieu
    - Khoan
    - ChuThe
    - HanhVi
    - HopDongLaoDong
    - TienLuong
    - ThoiGioLamViec
    - NghiPhep
    - XuLyKyLuat
    - CheDoBaoHiem
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

## Bước 5 — Viết Prompt entity extraction tiếng Việt

Tạo file `data/labor-law/prompts/entity_extraction_labor.txt`:

```
-Goal-
Cho đoạn văn bản thuộc Bộ luật Lao động Việt Nam hoặc các Nghị định hướng dẫn,
hãy trích xuất tất cả entity và mối quan hệ pháp lý.

-Entity Types-
VanBan, Chuong, Dieu, Khoan, ChuThe (Người lao động / Người sử dụng lao động / Cơ quan),
HanhVi, HopDongLaoDong, TienLuong, ThoiGioLamViec, NghiPhep, XuLyKyLuat, CheDoBaoHiem

-Ví dụ-
Văn bản: "Điều 35. Người lao động có quyền đơn phương chấm dứt hợp đồng lao động
nhưng phải báo trước cho người sử dụng lao động ít nhất 45 ngày nếu làm việc theo
hợp đồng lao động không xác định thời hạn."

Entities:
("entity"<|>"Điều 35"<|>"Dieu"<|>"Quy định quyền đơn phương chấm dứt HĐLĐ của NLĐ")
("entity"<|>"Người lao động"<|>"ChuThe"<|>"Chủ thể có quyền đơn phương chấm dứt HĐLĐ")
("entity"<|>"Người sử dụng lao động"<|>"ChuThe"<|>"Bên nhận thông báo chấm dứt HĐLĐ")
("entity"<|>"Đơn phương chấm dứt HĐLĐ"<|>"HanhVi"<|>"Hành vi chấm dứt hợp đồng một bên")
("entity"<|>"HĐLĐ không xác định thời hạn"<|>"HopDongLaoDong"<|>"Loại hợp đồng vô thời hạn")

Relations:
("relationship"<|>"Điều 35"<|>"Người lao động"<|>"entitles"<|>"Trao quyền đơn phương chấm dứt"<|>9)
("relationship"<|>"Điều 35"<|>"Người lao động"<|>"obligates"<|>"Phải báo trước 45 ngày"<|>9)
("relationship"<|>"Người lao động"<|>"Đơn phương chấm dứt HĐLĐ"<|>"requires"<|>"Điều kiện báo trước"<|>8)
```

---

## Kiểm tra hoàn thành

```bash
# Validate settings.yaml
graphrag init --root data/labor-law --force  # tạo cấu trúc
# Copy settings.yaml tùy chỉnh vào

# Kiểm tra entity types được nhận diện
python -c "
import yaml
cfg = yaml.safe_load(open('data/labor-law/settings.yaml'))
print('Entity types:', cfg['entity_extraction']['entity_types'])
"
```
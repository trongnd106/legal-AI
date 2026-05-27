# SKILL 04 — Multi-hop Reasoning, Retrieval & Đánh giá

> Áp dụng cho: checklist mục 4.1 → 5.5
> Stack: GraphRAG Query API · Python · pandas · extensible rule engine

---

## Mục tiêu

Triển khai các chế độ truy vấn (Global/Local Search), xây dựng multi-hop reasoning liên lĩnh vực, thêm rule-based validation layer có thể mở rộng theo domain, và đo lường hiệu quả.

---

## 1. Global Search — Câu hỏi tổng quát

Phù hợp khi câu hỏi liên quan đến nhiều Điều hoặc cần tổng hợp toàn bộ chủ đề pháp lý.

```python
# query/global_search.py
import asyncio
from graphrag.query.cli import run_global_search
from pathlib import Path

async def ask_global(
    question: str,
    root_dir: str = "./vn-legal-graphrag",
    domain_filter: str = None,     # "lao_dong" | "dan_su" | None (tất cả)
) -> dict:
    """
    Global search trên toàn bộ hệ thống pháp luật VN.
    domain_filter: giới hạn phạm vi nếu câu hỏi chỉ thuộc 1 lĩnh vực.
    """
    query = question
    if domain_filter:
        # Bổ sung context lĩnh vực vào query để community routing chính xác hơn
        DOMAIN_LABELS = {
            "lao_dong":     "luật lao động, quan hệ lao động, hợp đồng lao động",
            "dan_su":       "luật dân sự, giao dịch dân sự, hợp đồng dân sự",
            "hinh_su":      "luật hình sự, tội phạm, hình phạt",
            "doanh_nghiep": "luật doanh nghiệp, công ty, cổ đông",
            "dat_dai":      "luật đất đai, quyền sử dụng đất, đất ở",
        }
        domain_ctx = DOMAIN_LABELS.get(domain_filter, "")
        if domain_ctx:
            query = f"[Lĩnh vực: {domain_ctx}] {question}"

    result = await run_global_search(
        config_filepath=Path(root_dir) / "settings.yaml",
        data_dir=Path(root_dir) / "output",
        root_dir=root_dir,
        community_level=2,
        response_type="multiple paragraphs",
        query=query,
    )
    return {
        "answer": result.response,
        "domain_filter": domain_filter,
        "llm_calls": result.llm_calls,
        "prompt_tokens": result.prompt_tokens,
    }
```

---

## 2. Local Search — Câu hỏi cụ thể về Điều/Khoản

```python
# query/local_search.py
import asyncio, re
from graphrag.query.cli import run_local_search
from pathlib import Path

async def ask_local(
    question: str,
    root_dir: str = "./vn-legal-graphrag",
) -> dict:
    result = await run_local_search(
        config_filepath=Path(root_dir) / "settings.yaml",
        data_dir=Path(root_dir) / "output",
        root_dir=root_dir,
        community_level=2,
        response_type="single paragraph",
        query=question,
    )
    citations = _extract_article_citations(result.context_data)
    return {
        "answer":       result.response,
        "citations":    citations,
        "entities_used": result.context_data.get("entities", []),
    }

def _extract_article_citations(context_data: dict) -> list[str]:
    """Trích xuất số Điều/Khoản được dùng trong context."""
    citations = set()
    for item in context_data.get("sources", []):
        text = item.get("text", "")
        # Nhận dạng mọi dạng trích dẫn pháp lý VN
        for m in re.finditer(
            r"(?:Điều\s+\d+|Khoản\s+\d+\s+Điều\s+\d+|Điểm\s+[a-zđ]\s+Khoản\s+\d+\s+Điều\s+\d+)",
            text, re.IGNORECASE
        ):
            citations.add(m.group(0))
    return sorted(citations)
```

---

## 3. Multi-hop Reasoning Engine

Engine tổng quát hoạt động với mọi lĩnh vực pháp luật.

```python
# query/multihop_reasoning.py
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class ReasoningStep:
    entity_id:   str
    entity_name: str
    entity_type: str
    relation:    str
    description: str

@dataclass
class ReasoningChain:
    question:       str
    domain:         str
    steps:          list[ReasoningStep] = field(default_factory=list)
    cited_articles: list[str]          = field(default_factory=list)
    final_answer:   str                = ""
    method:         str                = ""

class VNLegalReasoningEngine:
    """
    Engine multi-hop reasoning tổng quát cho hệ thống pháp luật VN.
    Hỗ trợ mọi lĩnh vực; domain-specific logic được inject qua config.
    """

    # Chuỗi reasoning theo chủ đề — mỗi lĩnh vực có thể override
    CHAIN_TEMPLATES = {
        "violation": {
            "description": "Truy vết chuỗi: hành vi vi phạm → quy định → chế tài",
            "start_types": ["HANH_VI", "DIEU"],
            "hop_relations": ["penalizes", "cites", "obligates"],
            "end_types":    ["CHE_TAI", "NGHIA_VU"],
        },
        "entitlement": {
            "description": "Truy vết chuỗi: chủ thể → quyền lợi → điều kiện thụ hưởng",
            "start_types": ["CHU_THE"],
            "hop_relations": ["entitles", "requires_condition"],
            "end_types":    ["QUYEN", "DIEU_KIEN"],
        },
        "procedure": {
            "description": "Truy vết chuỗi: mục tiêu → thủ tục → cơ quan thực hiện",
            "start_types": ["THU_TUC", "HANH_VI"],
            "hop_relations": ["applies_to", "cites"],
            "end_types":    ["CO_QUAN", "THOI_HAN"],
        },
    }

    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = Path(artifacts_dir)
        self._load_graph()

    def _load_graph(self):
        self.entities      = pd.read_parquet(self.artifacts_dir / "create_final_entities.parquet")
        self.relationships = pd.read_parquet(self.artifacts_dir / "create_final_relationships.parquet")
        self.text_units    = pd.read_parquet(self.artifacts_dir / "create_final_text_units.parquet")
        print(f"✅ Graph loaded: {len(self.entities):,} entities, {len(self.relationships):,} rels")

    def find_entities(
        self,
        query: str,
        entity_types: list[str] = None,
        domain: str = None,
    ) -> pd.DataFrame:
        mask = self.entities['title'].str.contains(query, case=False, na=False)
        if entity_types:
            mask &= self.entities['type'].isin(entity_types)
        # domain filter dựa trên description nếu có tag domain trong metadata
        if domain:
            mask &= self.entities.get('description', pd.Series(dtype=str)).str.contains(
                domain, case=False, na=False
            )
        return self.entities[mask]

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: list[str] = None,
        direction: str = "both",        # "out" | "in" | "both"
    ) -> pd.DataFrame:
        if direction == "out":
            mask = self.relationships['source'] == entity_id
        elif direction == "in":
            mask = self.relationships['target'] == entity_id
        else:
            mask = (
                (self.relationships['source'] == entity_id) |
                (self.relationships['target'] == entity_id)
            )
        if relation_types:
            rel_mask = self.relationships['description'].str.contains(
                "|".join(relation_types), case=False, na=False
            )
            mask &= rel_mask
        return self.relationships[mask]

    def trace_chain(
        self,
        start_query: str,
        chain_type: str = "violation",
        domain: str = None,
        max_hops: int = 3,
    ) -> ReasoningChain:
        """
        Suy luận multi-hop tổng quát theo template chain_type.

        Ví dụ gọi:
          # Luật Lao động: không đóng BHXH → vi phạm điều nào → phạt bao nhiêu
          engine.trace_chain("không đóng bảo hiểm xã hội", "violation", "lao_dong")

          # Luật Dân sự: giao dịch vô hiệu → hậu quả pháp lý → hoàn trả tài sản
          engine.trace_chain("giao dịch dân sự vô hiệu", "violation", "dan_su")

          # Luật Doanh nghiệp: thành lập công ty → thủ tục → cơ quan đăng ký
          engine.trace_chain("thành lập công ty TNHH", "procedure", "doanh_nghiep")
        """
        template = self.CHAIN_TEMPLATES.get(chain_type, self.CHAIN_TEMPLATES["violation"])
        chain    = ReasoningChain(question=start_query, domain=domain or "all", method=chain_type)

        # Bước 1: tìm entity xuất phát
        start_entities = self.find_entities(
            start_query, entity_types=template["start_types"], domain=domain
        )
        if start_entities.empty:
            # Thử tìm rộng hơn không filter entity_type
            start_entities = self.find_entities(start_query, domain=domain)
        if start_entities.empty:
            chain.final_answer = f"Không tìm thấy '{start_query}' trong Knowledge Graph."
            return chain

        current_entity = start_entities.iloc[0]
        chain.steps.append(ReasoningStep(
            entity_id=current_entity['id'],
            entity_name=current_entity['title'],
            entity_type=current_entity.get('type', ''),
            relation="start",
            description=str(current_entity.get('description', ''))[:150],
        ))

        # Các bước hop
        visited = {current_entity['id']}
        for hop in range(max_hops):
            neighbors = self.get_neighbors(
                current_entity['id'],
                relation_types=template["hop_relations"],
            )
            if neighbors.empty:
                break

            for _, rel in neighbors.head(3).iterrows():
                neighbor_id = (
                    rel['target'] if rel['source'] == current_entity['id']
                    else rel['source']
                )
                if neighbor_id in visited:
                    continue

                neighbor_row = self.entities[self.entities['id'] == neighbor_id]
                if neighbor_row.empty:
                    continue

                nb = neighbor_row.iloc[0]
                chain.steps.append(ReasoningStep(
                    entity_id=neighbor_id,
                    entity_name=nb['title'],
                    entity_type=nb.get('type', ''),
                    relation=str(rel.get('description', '')),
                    description=str(nb.get('description', ''))[:150],
                ))

                # Ghi nhận nếu là Điều luật
                if "Điều" in nb['title'] or nb.get('type') == 'DIEU':
                    chain.cited_articles.append(nb['title'])

                visited.add(neighbor_id)

                # Dừng nếu đã đến end_type
                if nb.get('type') in template["end_types"]:
                    break

            if chain.steps and chain.steps[-1].entity_type in template["end_types"]:
                break
            current_entity = self.entities[
                self.entities['id'] == chain.steps[-1].entity_id
            ].iloc[0] if not self.entities[
                self.entities['id'] == chain.steps[-1].entity_id
            ].empty else current_entity

        chain.final_answer = self._format_answer(chain)
        return chain

    def _format_answer(self, chain: ReasoningChain) -> str:
        if len(chain.steps) <= 1:
            return "Không đủ thông tin để suy luận đa bước."
        lines = [f"Chuỗi suy luận cho: '{chain.question}'"]
        for i, step in enumerate(chain.steps):
            prefix = "📌" if i == 0 else f"  {'→'*i}"
            lines.append(f"{prefix} [{step.entity_type}] {step.entity_name}")
            if step.relation != "start":
                lines.append(f"     Quan hệ: {step.relation}")
        if chain.cited_articles:
            lines.append(f"\nCăn cứ pháp lý: {', '.join(chain.cited_articles)}")
        return "\n".join(lines)

    def detect_chain_type(self, question: str) -> str:
        """Tự động phát hiện loại chuỗi suy luận từ câu hỏi."""
        import re
        q = question.lower()
        if re.search(r"phạt|chế tài|bồi thường|xử lý|vi phạm|tội", q):
            return "violation"
        if re.search(r"thủ tục|đăng ký|hồ sơ|cơ quan|nộp", q):
            return "procedure"
        if re.search(r"quyền|được hưởng|được nhận|lợi ích", q):
            return "entitlement"
        return "violation"     # default
```

---

## 4. Temporal Filter — Lọc theo hiệu lực

```python
# query/temporal_filter.py
"""
Lọc kết quả theo tình trạng hiệu lực của văn bản pháp luật.
Tích hợp vào pipeline sau bước retrieval, trước khi trả kết quả.
"""
from datetime import date
import json, re

def load_effectiveness_index(
    meta_path: str = "data/processed/all_articles_meta.json"
) -> dict:
    """
    Tạo index: van_ban_id → {tinh_trang, ngay_hieu_luc, het_hieu_luc_boi}
    """
    with open(meta_path, encoding="utf-8") as f:
        articles = json.load(f)

    index = {}
    for art in articles:
        vid = art["van_ban_id"]
        if vid not in index:
            index[vid] = {
                "tinh_trang":        art.get("tinh_trang", "con_hieu_luc"),
                "ngay_hieu_luc":     art.get("ngay_hieu_luc", ""),
                "ten_van_ban":       art.get("ten_van_ban", ""),
            }
    return index

EFFECTIVENESS_INDEX = None

def is_effective(van_ban_id: str, as_of: date = None) -> bool:
    """Kiểm tra văn bản còn hiệu lực tại thời điểm as_of (mặc định: hôm nay)."""
    global EFFECTIVENESS_INDEX
    if EFFECTIVENESS_INDEX is None:
        EFFECTIVENESS_INDEX = load_effectiveness_index()

    as_of = as_of or date.today()
    info  = EFFECTIVENESS_INDEX.get(van_ban_id)
    if not info:
        return True    # không có thông tin → giả định còn hiệu lực

    if info["tinh_trang"] == "het_hieu_luc":
        return False

    if info["ngay_hieu_luc"]:
        try:
            hieu_luc_date = date.fromisoformat(info["ngay_hieu_luc"])
            if as_of < hieu_luc_date:
                return False    # chưa có hiệu lực
        except ValueError:
            pass

    return True

def filter_citations_by_effectiveness(citations: list[str], context_data: dict) -> dict:
    """
    Bổ sung cảnh báo vào câu trả lời nếu citation từ văn bản hết hiệu lực.
    """
    warnings = []
    for cite in citations:
        # Trích van_ban_id từ cite text nếu có (VD: "Điều 35 NĐ 90/2019")
        nd_match = re.search(r"(NĐ|Nghị định|TT|Thông tư)\s+([\d/\w\-]+)", cite)
        if nd_match:
            van_ban_id = nd_match.group(2).replace("/", "_")
            if not is_effective(van_ban_id):
                warnings.append(
                    f"⚠️ '{cite}' có thể đã hết hiệu lực. Kiểm tra tại vbpl.vn."
                )
    return {"warnings": warnings}
```

---

## 5. Rule-based Validation Layer (extensible theo domain)

```python
# query/rule_validator.py
"""
Validate kết quả LLM với các quy tắc cứng từ pháp luật.
Dễ mở rộng: thêm domain mới = thêm 1 entry vào DOMAIN_RULES.
"""
import re
from dataclasses import dataclass

@dataclass
class ValidationResult:
    is_valid:    bool
    warnings:    list[str]
    corrections: list[str]

# === Quy tắc theo từng lĩnh vực ===
DOMAIN_RULES = {

    "lao_dong": {
        "luong_toi_thieu_vung": {           # NĐ 74/2024
            "vung_I":  4_960_000,
            "vung_II": 4_410_000,
            "vung_III":3_860_000,
            "vung_IV": 3_450_000,
        },
        "gio_lam_toi_da_ngay":   8,         # Điều 105 BLLĐ
        "gio_lam_toi_da_tuan":   48,
        "them_gio_toi_da_ngay":  4,
        "nghi_phep_toi_thieu":   12,        # ngày/năm, Điều 113
    },

    "dan_su": {
        "thoi_hieu_khoi_kien_chung": 3,     # năm, Điều 429 BLDS
        "thoi_hieu_yeu_cau_tuyen_vo_hieu": 2,  # năm, Điều 132
        "lai_suat_cho_vay_toi_da": 20,      # %/năm, Điều 468
    },

    "hinh_su": {
        "tuoi_toi_thieu_trach_nhiem_hs": 14,  # tuổi, Điều 12
        "tuoi_day_du_trach_nhiem_hs":    16,
    },

    "doanh_nghiep": {
        "von_dieu_le_toi_thieu_cty_luat": 10_000_000_000,  # đồng, Luật Luật sư
    },

    "thue": {
        "thue_gtgt_pho_thong":  10,         # %
        "thue_gtgt_uu_dai":      5,
        "thue_thu_nhap_ca_nhan_toi_da": 35, # %
    },
}

def validate_answer(
    answer: str,
    domain: str,
    question_keywords: list[str] = None,
) -> ValidationResult:
    """
    Kiểm tra câu trả lời LLM không vi phạm quy tắc cứng của domain.
    """
    warnings    = []
    corrections = []
    rules       = DOMAIN_RULES.get(domain, {})
    q_keywords  = [k.lower() for k in (question_keywords or [])]

    # === Luật Lao động ===
    if domain == "lao_dong":
        # Kiểm tra mức lương
        if any(k in q_keywords for k in ["lương", "tiền lương", "lương tối thiểu"]):
            amounts = re.findall(r"(\d[\d.,]+)\s*(đồng|triệu)?", answer)
            for amt_str, unit in amounts:
                try:
                    amt = float(amt_str.replace(",", "").replace(".", ""))
                    if unit == "triệu":
                        amt *= 1_000_000
                    min_wage = rules.get("luong_toi_thieu_vung", {}).get("vung_IV", 3_450_000)
                    if 100_000 < amt < min_wage:
                        warnings.append(
                            f"⚠️ Mức lương {amt:,.0f}đ thấp hơn lương tối thiểu vùng IV "
                            f"({min_wage:,}đ/tháng theo NĐ 74/2024)"
                        )
                except ValueError:
                    pass

        # Kiểm tra giờ làm
        if any(k in q_keywords for k in ["giờ làm", "làm thêm", "giờ"]):
            hours = re.findall(r"(\d+)\s*giờ", answer)
            max_per_day = rules.get("gio_lam_toi_da_ngay", 8) + rules.get("them_gio_toi_da_ngay", 4)
            for h in hours:
                if int(h) > max_per_day:
                    warnings.append(
                        f"⚠️ {h} giờ/ngày vượt giới hạn tối đa ({max_per_day} giờ/ngày, Điều 105 BLLĐ)"
                    )

    # === Luật Dân sự ===
    elif domain == "dan_su":
        if any(k in q_keywords for k in ["thời hiệu", "khởi kiện", "yêu cầu"]):
            years = re.findall(r"(\d+)\s*năm", answer)
            for y in years:
                if int(y) > 10:
                    warnings.append(
                        f"⚠️ Thời hiệu {y} năm có thể không chính xác — "
                        f"kiểm tra Điều 429 và các điều khoản thời hiệu đặc biệt BLDS 2015"
                    )

        # Kiểm tra lãi suất cho vay
        if any(k in q_keywords for k in ["lãi suất", "lãi", "cho vay"]):
            rates = re.findall(r"(\d+(?:\.\d+)?)\s*%", answer)
            max_rate = rules.get("lai_suat_cho_vay_toi_da", 20)
            for r in rates:
                if float(r) > max_rate:
                    warnings.append(
                        f"⚠️ Lãi suất {r}%/năm vượt trần {max_rate}%/năm "
                        f"(Điều 468 BLDS 2015)"
                    )

    # === Luật Hình sự ===
    elif domain == "hinh_su":
        if any(k in q_keywords for k in ["tuổi", "vị thành niên", "người chưa thành niên"]):
            ages = re.findall(r"(\d+)\s*tuổi", answer)
            for a in ages:
                if int(a) < rules.get("tuoi_toi_thieu_trach_nhiem_hs", 14):
                    warnings.append(
                        f"⚠️ Người dưới {rules['tuoi_toi_thieu_trach_nhiem_hs']} tuổi "
                        f"không chịu trách nhiệm hình sự (Điều 12 BLHS)"
                    )

    return ValidationResult(
        is_valid=len(warnings) == 0,
        warnings=warnings,
        corrections=corrections,
    )
```

---

## 6. Bộ test cases đa lĩnh vực

```python
# tests/evaluation_suite.py
"""
Bộ test cases đa lĩnh vực với ground truth.
Mỗi test case gắn domain để đo accuracy theo lĩnh vực.
"""

TEST_CASES = [

    # ===================== LUẬT LAO ĐỘNG =====================
    {
        "id": "LD001", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "easy",
        "question": "Người lao động có bao nhiêu ngày nghỉ phép năm tối thiểu?",
        "expected_keywords": ["12 ngày", "Điều 113"],
        "expected_citations": ["Điều 113"],
    },
    {
        "id": "LD002", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "easy",
        "question": "Lương tối thiểu vùng I hiện tại là bao nhiêu?",
        "expected_keywords": ["4.960.000", "vùng I"],
        "expected_citations": ["Điều 91"],
    },
    {
        "id": "LD010", "domain": "lao_dong",
        "category": "multi_hop", "difficulty": "medium",
        "question": "Người sử dụng lao động không trả trợ cấp thôi việc thì bị xử lý thế nào?",
        "expected_keywords": ["Điều 46", "xử phạt", "trợ cấp"],
        "expected_citations": ["Điều 46"],
        "reasoning_chain": "Điều 46 (nghĩa vụ) → NĐ 12/2022 (chế tài)",
    },
    {
        "id": "LD011", "domain": "lao_dong",
        "category": "multi_hop", "difficulty": "hard",
        "question": "NLĐ đơn phương chấm dứt đúng pháp luật có được trợ cấp thôi việc không và cần điều kiện gì?",
        "expected_keywords": ["báo trước", "Điều 35", "Điều 46"],
        "expected_citations": ["Điều 35", "Điều 46"],
        "reasoning_chain": "Điều 35 (quyền) → Điều 46 (hậu quả tài chính)",
    },

    # ===================== LUẬT DÂN SỰ =====================
    {
        "id": "DS001", "domain": "dan_su",
        "category": "single_hop", "difficulty": "easy",
        "question": "Điều kiện để giao dịch dân sự có hiệu lực là gì?",
        "expected_keywords": ["Điều 117", "năng lực hành vi", "tự nguyện"],
        "expected_citations": ["Điều 117"],
    },
    {
        "id": "DS010", "domain": "dan_su",
        "category": "multi_hop", "difficulty": "medium",
        "question": "Hợp đồng vô hiệu do giả tạo thì hậu quả pháp lý là gì?",
        "expected_keywords": ["Điều 124", "vô hiệu", "hoàn trả"],
        "expected_citations": ["Điều 124", "Điều 131"],
        "reasoning_chain": "Điều 124 (vô hiệu giả tạo) → Điều 131 (hậu quả)",
    },
    {
        "id": "DS011", "domain": "dan_su",
        "category": "multi_hop", "difficulty": "hard",
        "question": "Thời hiệu khởi kiện tranh chấp hợp đồng mua bán tài sản là bao nhiêu năm?",
        "expected_keywords": ["3 năm", "Điều 429", "thời hiệu"],
        "expected_citations": ["Điều 429"],
    },

    # ===================== LUẬT DOANH NGHIỆP =====================
    {
        "id": "DN001", "domain": "doanh_nghiep",
        "category": "single_hop", "difficulty": "easy",
        "question": "Thủ tục đăng ký thành lập công ty TNHH gồm những bước nào?",
        "expected_keywords": ["hồ sơ", "Phòng đăng ký kinh doanh", "Điều 22"],
        "expected_citations": ["Điều 22"],
    },
    {
        "id": "DN010", "domain": "doanh_nghiep",
        "category": "multi_hop", "difficulty": "medium",
        "question": "Giám đốc công ty TNHH 2 thành viên có những quyền hạn gì và chịu trách nhiệm gì?",
        "expected_keywords": ["Điều 63", "quyền", "trách nhiệm", "Hội đồng thành viên"],
        "expected_citations": ["Điều 63"],
    },

    # ===================== LUẬT HÌNH SỰ =====================
    {
        "id": "HS001", "domain": "hinh_su",
        "category": "single_hop", "difficulty": "easy",
        "question": "Người bao nhiêu tuổi thì chịu trách nhiệm hình sự?",
        "expected_keywords": ["14 tuổi", "16 tuổi", "Điều 12"],
        "expected_citations": ["Điều 12"],
    },
    {
        "id": "HS010", "domain": "hinh_su",
        "category": "multi_hop", "difficulty": "hard",
        "question": "Tội lừa đảo chiếm đoạt tài sản trên 500 triệu đồng thì hình phạt tối đa là gì?",
        "expected_keywords": ["Điều 174", "phạt tù", "20 năm"],
        "expected_citations": ["Điều 174"],
    },

    # ===================== TEMPORAL =====================
    {
        "id": "TMP001", "domain": "lao_dong",
        "category": "temporal", "difficulty": "medium",
        "question": "Nghị định quy định lương tối thiểu vùng hiện đang có hiệu lực là nghị định nào?",
        "expected_keywords": ["còn hiệu lực", "NĐ 74/2024"],
        "expected_citations": [],
    },

    # ===================== CROSS-DOMAIN =====================
    {
        "id": "CD001",
        "domain": "cross_domain",   # câu hỏi liên quan 2 lĩnh vực
        "category": "cross_domain", "difficulty": "hard",
        "question": "Công ty vi phạm luật lao động (không đóng BHXH) thì ngoài phạt hành chính còn có thể bị xử lý thế nào theo luật hình sự?",
        "expected_keywords": ["Điều 216", "tội trốn đóng BHXH", "hành chính"],
        "expected_citations": ["Điều 216"],
        "reasoning_chain": "NĐ 12/2022 (phạt hành chính) → Điều 216 BLHS (hình sự)",
    },
]

def evaluate_system(answer_fn, test_cases=TEST_CASES) -> dict:
    """
    answer_fn: function(question: str, domain: str) ->
               {"answer": str, "cited_articles": list[str]}
    """
    results = {
        "total": len(test_cases),
        "keyword_hits": 0, "citation_hits": 0,
        "by_domain": {}, "by_category": {},
    }

    for tc in test_cases:
        response     = answer_fn(tc["question"], tc.get("domain", ""))
        answer_lower = response.get("answer", "").lower()
        citations    = response.get("cited_articles", [])

        kw_hit = all(kw.lower() in answer_lower for kw in tc["expected_keywords"])
        cite_hit = (
            not tc["expected_citations"] or
            any(
                any(exp in cite for cite in citations)
                for exp in tc["expected_citations"]
            )
        )

        for bucket_key, bucket_val in [("domain", tc["domain"]), ("category", tc["category"])]:
            b = results[f"by_{bucket_key}"].setdefault(
                bucket_val, {"total": 0, "keyword_hits": 0, "citation_hits": 0}
            )
            b["total"] += 1
            if kw_hit:   b["keyword_hits"] += 1
            if cite_hit: b["citation_hits"] += 1

        if kw_hit:   results["keyword_hits"] += 1
        if cite_hit: results["citation_hits"] += 1

    results["keyword_accuracy"]  = results["keyword_hits"]  / results["total"]
    results["citation_accuracy"] = results["citation_hits"] / results["total"]

    print(f"\n=== KẾT QUẢ ĐÁNH GIÁ ===")
    print(f"Tổng: {results['total']} test cases")
    print(f"Keyword Accuracy : {results['keyword_accuracy']:.1%}")
    print(f"Citation Accuracy: {results['citation_accuracy']:.1%}")

    print(f"\nTheo Domain:")
    for domain, stats in results["by_domain"].items():
        kw = stats["keyword_hits"] / stats["total"]
        print(f"  {domain:20s}: {kw:.1%} ({stats['keyword_hits']}/{stats['total']})")

    print(f"\nTheo Category:")
    for cat, stats in results["by_category"].items():
        kw = stats["keyword_hits"] / stats["total"]
        print(f"  {cat:15s}: {kw:.1%} ({stats['keyword_hits']}/{stats['total']})")

    return results
```

---

## Checklist hoàn thành mục này

- [ ] `ask_global()` với `domain_filter=None` trả lời được câu hỏi tổng quát liên lĩnh vực
- [ ] `ask_global()` với `domain_filter="lao_dong"` cho kết quả tốt hơn câu hỏi chỉ về lao động
- [ ] `ask_local()` trả về `citations` chứa số Điều cụ thể
- [ ] `VNLegalReasoningEngine.trace_chain()` chạy được với 3 `chain_type` khác nhau
- [ ] `validate_answer()` hoạt động đúng với ít nhất 3 domain (`lao_dong`, `dan_su`, `hinh_su`)
- [ ] Bộ test cases có ≥ 50 cases, bao gồm ≥ 3 domain và có ít nhất 3 `cross_domain` cases
- [ ] Keyword Accuracy ≥ 70% tổng thể
- [ ] Citation Accuracy ≥ 60% tổng thể
- [ ] Cross-domain Accuracy ≥ 50% (câu hỏi liên 2 lĩnh vực pháp luật)

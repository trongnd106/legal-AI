"""
query/multihop_reasoning.py — Multi-hop Reasoning Engine trên merged Knowledge Graph.

Sử dụng merged_entities.parquet và merged_relationships.parquet (output từ
02_merge_structural_graph.py) để suy luận đa bước qua Knowledge Graph.

Lưu ý về entity type names:
    - L1 (structural): "Dieu", "Khoan", "VanBan", "Chuong", "CoQuan"  (giữ nguyên case)
    - L2 (LLM):        "CHUTHE", "HANHVI", "CHETAI", "XULYKYLUAT",
                       "HOPDONGLAODONG", "TIENLUONG", "NGHIPHEP", ...  (UPPERCASE)
    Vì GraphRAG chạy .upper() lên entity_type khi parse LLM output.

Lưu ý về relationship description:
    - L1: đúng bằng tên relation type ("contains", "issued_by", "guided_by", ...)
    - L2: đúng bằng tên relation type ("entitles", "obligates", "penalizes", ...)
    Vì prompt của chúng ta đặt relation_type ở field[3] — GraphRAG map field[3] → description.

Vì vậy lọc bằng description.str.contains() là chính xác.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from query.loader import GraphLoader


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ReasoningStep:
    entity_id:   str
    entity_name: str
    entity_type: str
    relation:    str          # relation type (description)
    description: str          # mô tả ngắn entity


@dataclass
class ReasoningChain:
    question:        str
    domain:          str
    chain_type:      str
    steps:           list[ReasoningStep] = field(default_factory=list)
    cited_articles:  list[str]           = field(default_factory=list)
    final_answer:    str                 = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class VNLegalReasoningEngine:
    """
    Multi-hop reasoning engine trên merged Knowledge Graph (L1 + L2).

    Cách dùng:
        loader = GraphLoader("data/labor-law").load()
        engine = VNLegalReasoningEngine(loader)
        chain  = engine.trace_chain("không đóng bảo hiểm xã hội", "violation")
        print(chain.final_answer)
    """

    # -----------------------------------------------------------------------
    # Chain templates — entity types dùng case-insensitive comparison
    # -----------------------------------------------------------------------
    CHAIN_TEMPLATES: dict[str, dict] = {
        "violation": {
            "description":  "Truy vết: hành vi vi phạm → quy định pháp luật → chế tài",
            "start_types":  ["HANHVI", "Dieu"],
            "hop_relations": ["penalizes", "disciplines", "obligates", "cites"],
            "end_types":    ["CHETAI", "XULYKYLUAT"],
        },
        "entitlement": {
            "description":  "Truy vết: chủ thể → quyền lợi → điều kiện thụ hưởng",
            "start_types":  ["CHUTHE", "Dieu"],
            "hop_relations": ["entitles", "requires_condition", "applies_to"],
            "end_types":    ["NGHIPHEP", "TIENLUONG", "CHEDOBAOHIEM", "TROCAPTHOIVIEC"],
        },
        "procedure": {
            "description":  "Truy vết: mục tiêu → quy trình → cơ quan thực hiện",
            "start_types":  ["HANHVI", "Dieu", "HOPDONGLAODONG"],
            "hop_relations": ["applies_to", "cites", "enforced_by", "guided_by"],
            "end_types":    ["CoQuan"],
        },
    }

    def __init__(self, loader: GraphLoader):
        self.loader = loader
        merged_ents, merged_rels = loader.load_merged_graph()
        self.entities      = merged_ents
        self.relationships = merged_rels
        # Normalize cho tìm kiếm
        self._ent_upper    = self.entities["title"].str.upper()
        self._type_upper   = self.entities["type"].str.upper().fillna("")

    # -----------------------------------------------------------------------
    # Core graph operations
    # -----------------------------------------------------------------------
    def find_entities(
        self,
        query: str,
        entity_types: list[str] | None = None,
        domain: str | None = None,
    ) -> pd.DataFrame:
        """
        Tìm entity theo tên hoặc mô tả.
        entity_types: so sánh case-insensitive.
        """
        mask = self._ent_upper.str.contains(query.upper(), regex=False, na=False)
        if not mask.any():
            # Fallback: tìm trong description
            mask = self.entities["description"].str.contains(
                query, case=False, na=False
            )
        if entity_types:
            type_upper = [t.upper() for t in entity_types]
            mask &= self._type_upper.isin(type_upper)
        if domain:
            mask &= self.entities["description"].str.contains(
                domain, case=False, na=False
            )
        return self.entities[mask].reset_index(drop=True)

    def get_neighbors(
        self,
        entity_title: str,
        relation_types: list[str] | None = None,
        direction: str = "both",       # "out" | "in" | "both"
    ) -> pd.DataFrame:
        """
        Lấy các relation liên kết với entity_title.

        Lưu ý: relationship source/target lưu entity title (uppercase cho L2, gốc cho L1).
        So sánh case-insensitive để an toàn.
        """
        src = self.relationships["source"].str.upper()
        tgt = self.relationships["target"].str.upper()
        title_up = entity_title.upper()

        if direction == "out":
            mask = src == title_up
        elif direction == "in":
            mask = tgt == title_up
        else:
            mask = (src == title_up) | (tgt == title_up)

        if relation_types:
            rel_pattern = "|".join(re.escape(r) for r in relation_types)
            rel_mask = self.relationships["description"].str.contains(
                rel_pattern, case=False, na=False, regex=True
            )
            mask = mask & rel_mask

        return self.relationships[mask].reset_index(drop=True)

    def get_entity_by_title(self, title: str) -> pd.Series | None:
        """Tìm entity row theo title (case-insensitive)."""
        rows = self.entities[self._ent_upper == title.upper()]
        return rows.iloc[0] if not rows.empty else None

    # -----------------------------------------------------------------------
    # Trace chain
    # -----------------------------------------------------------------------
    def trace_chain(
        self,
        start_query: str,
        chain_type: str = "violation",
        domain: str | None = None,
        max_hops: int = 4,
    ) -> ReasoningChain:
        """
        Suy luận multi-hop theo template.

        Ví dụ:
            # Không đóng BHXH → vi phạm điều nào → bị phạt bao nhiêu
            engine.trace_chain("không đóng bảo hiểm xã hội", "violation", "lao_dong")

            # NLĐ được hưởng nghỉ phép theo điều kiện gì
            engine.trace_chain("nghỉ phép năm", "entitlement", "lao_dong")

            # Thủ tục xử lý kỷ luật sa thải
            engine.trace_chain("sa thải", "procedure", "lao_dong")
        """
        template = self.CHAIN_TEMPLATES.get(chain_type, self.CHAIN_TEMPLATES["violation"])
        chain    = ReasoningChain(
            question=start_query, domain=domain or "all", chain_type=chain_type
        )

        # Bước 1: tìm entity xuất phát
        start_ents = self.find_entities(
            start_query, entity_types=template["start_types"], domain=domain
        )
        if start_ents.empty:
            start_ents = self.find_entities(start_query, domain=domain)
        if start_ents.empty:
            chain.final_answer = f"Không tìm thấy '{start_query}' trong Knowledge Graph."
            return chain

        current = start_ents.iloc[0]
        chain.steps.append(ReasoningStep(
            entity_id=str(current.get("id", "")),
            entity_name=str(current["title"]),
            entity_type=str(current.get("type", "")),
            relation="start",
            description=str(current.get("description", ""))[:200],
        ))
        self._record_article(chain, current)

        # Bước 2–N: hop qua relations
        visited_titles: set[str] = {str(current["title"]).upper()}
        for _ in range(max_hops):
            neighbors = self.get_neighbors(
                current["title"],
                relation_types=template["hop_relations"],
            )
            if neighbors.empty:
                break

            advanced = False
            for _, rel in neighbors.head(5).iterrows():
                src_up = str(rel["source"]).upper()
                tgt_up = str(rel["target"]).upper()
                cur_up = str(current["title"]).upper()

                neighbor_title = rel["target"] if src_up == cur_up else rel["source"]
                if str(neighbor_title).upper() in visited_titles:
                    continue

                nb = self.get_entity_by_title(str(neighbor_title))
                if nb is None:
                    continue

                chain.steps.append(ReasoningStep(
                    entity_id=str(nb.get("id", "")),
                    entity_name=str(nb["title"]),
                    entity_type=str(nb.get("type", "")),
                    relation=str(rel.get("description", "")),
                    description=str(nb.get("description", ""))[:200],
                ))
                self._record_article(chain, nb)
                visited_titles.add(str(nb["title"]).upper())
                current  = nb
                advanced = True

                # Dừng nếu đến end_type
                if nb.get("type", "").upper() in [t.upper() for t in template["end_types"]]:
                    break

            if not advanced:
                break

            # Nếu đang ở end_type thì dừng
            if current.get("type", "").upper() in [t.upper() for t in template["end_types"]]:
                break

        chain.final_answer = self._format_answer(chain)
        return chain

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _record_article(self, chain: ReasoningChain, entity: pd.Series) -> None:
        """Ghi nhận nếu entity là Điều luật."""
        title = str(entity.get("title", ""))
        etype = str(entity.get("type", "")).upper()
        if "ĐIỀU" in title.upper() or etype in ("DIEU", "ĐIỀU"):
            if title not in chain.cited_articles:
                chain.cited_articles.append(title)

    def _format_answer(self, chain: ReasoningChain) -> str:
        if len(chain.steps) <= 1:
            return "Không đủ thông tin để suy luận đa bước."
        lines = [f"Chuỗi suy luận cho: '{chain.question}'"]
        for i, step in enumerate(chain.steps):
            arrow = "📌" if i == 0 else ("  " + "→" * i)
            lines.append(f"{arrow} [{step.entity_type}] {step.entity_name}")
            if step.relation != "start":
                lines.append(f"     -- {step.relation} -->")
            if step.description:
                short = step.description[:120].replace("\n", " ")
                lines.append(f"     {short}")
        if chain.cited_articles:
            lines.append(f"\nCăn cứ pháp lý: {', '.join(chain.cited_articles)}")
        return "\n".join(lines)

    def detect_chain_type(self, question: str) -> str:
        """Tự động phát hiện loại chuỗi suy luận từ câu hỏi."""
        q = question.lower()
        if re.search(r"phạt|chế tài|bồi thường|xử lý|vi phạm|tội|kỷ luật", q):
            return "violation"
        if re.search(r"thủ tục|đăng ký|hồ sơ|cơ quan|nộp|trình tự", q):
            return "procedure"
        if re.search(r"quyền|được hưởng|được nhận|lợi ích|trợ cấp|nghỉ phép", q):
            return "entitlement"
        return "violation"


# ---------------------------------------------------------------------------
# Ví dụ CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    root  = sys.argv[1] if len(sys.argv) > 1 else "data/labor-law"
    query = sys.argv[2] if len(sys.argv) > 2 else "không đóng bảo hiểm xã hội"
    chain_type = sys.argv[3] if len(sys.argv) > 3 else None

    loader = GraphLoader(root).load()
    engine = VNLegalReasoningEngine(loader)

    ct = chain_type or engine.detect_chain_type(query)
    result = engine.trace_chain(query, chain_type=ct, domain="lao_dong")
    print(result.final_answer)

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
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from query.loader import GraphLoader


_VN_CHARS = str.maketrans({
    "đ": "d", "Đ": "D",
    "ă": "a", "Ă": "A", "â": "a", "Â": "A",
    "ê": "e", "Ê": "E", "ô": "o", "Ô": "O",
    "ơ": "o", "Ơ": "O", "ư": "u", "Ư": "U",
})


def _strip_diacritics(text: str) -> str:
    """Chuyển 'lao động' → 'lao dong', 'Quốc hội' → 'Quoc hoi' v.v."""
    text = text.translate(_VN_CHARS)
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


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
    # hop_relations dùng Vietnamese keywords vì L2 relationship descriptions
    # là văn xuôi tiếng Việt (VD: "Bị xử phạt bằng", "Có quyền thực hiện", …)
    # -----------------------------------------------------------------------
    # Entity types thuần L2 (có relationships ngữ nghĩa phong phú)
    _L2_TYPES = {"HANHVI", "CHUTHE", "CHETAI", "TIENLUONG", "NGHIPHEP",
                 "CHEDOBAOHIEM", "TROCAPTHOIVIEC", "XULYKYLUAT",
                 "HOPDONGLAODONG", "THOIGIOLAMVIEC", "ANTOANVESINHLAODONG",
                 "TRALUONG", "COQUAN"}

    CHAIN_TEMPLATES: dict[str, dict] = {
        "violation": {
            "description":  "Truy vết: hành vi vi phạm → quy định pháp luật → chế tài",
            "start_types":  ["HANHVI", "Dieu"],
            "hop_relations": ["xử phạt", "cấm thực hiện"],
            "end_types":    ["CHETAI", "XULYKYLUAT"],
        },
        "entitlement": {
            "description":  "Truy vết: chủ thể → quyền lợi → điều kiện thụ hưởng",
            "start_types":  ["CHUTHE", "Dieu"],
            "hop_relations": ["quyền", "nghĩa vụ", "áp dụng đối với", "bao gồm"],
            "end_types":    ["NGHIPHEP", "TIENLUONG", "CHEDOBAOHIEM", "TROCAPTHOIVIEC"],
        },
        "procedure": {
            "description":  "Truy vết: mục tiêu → quy trình → cơ quan thực hiện",
            "start_types":  ["HANHVI", "Dieu", "HOPDONGLAODONG"],
            "hop_relations": ["có thẩm quyền", "trách nhiệm thực hiện", "liên quan đến"],
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
    def _domain_filter(self, df: pd.DataFrame, domain: str) -> pd.DataFrame | None:
        """
        Áp dụng domain filter với Unicode normalization cho tiếng Việt.

        Kiểm tra BOTH description và title (fallback). Nếu filter quét hết
        toàn bộ thì trả về unfiltered (tránh false negative do domain
        keyword không xuất hiện trong description entity cụ thể).
        """
        norm_domain = _strip_diacritics(domain.replace("_", " ")).strip().lower()
        if not norm_domain:
            return df
        norm_desc = df["description"].apply(
            lambda x: _strip_diacritics(str(x)) if pd.notna(x) else ""
        )
        desc_match = norm_desc.str.contains(norm_domain, case=False, na=False)
        norm_title = df["title"].apply(
            lambda x: _strip_diacritics(str(x)) if pd.notna(x) else ""
        )
        title_match = norm_title.str.contains(norm_domain, case=False, na=False)
        combined = desc_match | title_match
        if not combined.any():
            return df  # soft fallback — không quét hết
        return df[combined]

    def _keyword_score(self, keywords: list[str]) -> pd.Series:
        """Đếm số keywords xuất hiện trong mỗi entity description (0..N)."""
        score = pd.Series(0, index=self.entities.index, dtype=int)
        for kw in keywords:
            mask = self.entities["description"].str.contains(
                kw, case=False, na=False, regex=False
            )
            score = score + mask.astype(int)
        return score

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
        mask = self._ent_upper.str.contains(query.upper(), na=False, regex=False)
        if mask.any():
            if entity_types:
                type_upper = [t.upper() for t in entity_types]
                mask &= self._type_upper.isin(type_upper)
            result = self.entities[mask]
            if domain is not None and not result.empty:
                result = self._domain_filter(result, domain)
            return result.sort_values("id").reset_index(drop=True)

        # Fallback: scoring-based keyword matching
        keywords = [w.strip() for w in re.split(r"[,;\s]+", query) if len(w.strip()) > 2]
        if not keywords:
            return pd.DataFrame()

        score = self._keyword_score(keywords)
        if entity_types:
            type_upper = [t.upper() for t in entity_types]
            type_mask = self._type_upper.isin(type_upper)
            score = score[type_mask]

        # Chỉ giữ entity có ít nhất 2 keywords match (hoặc ≥30% nếu nhiều kw)
        threshold = max(2, len(keywords) // 3)
        candidates = score[score >= threshold].sort_values(ascending=False)
        if candidates.empty:
            return pd.DataFrame()

        result = self.entities.loc[candidates.index]
        if domain is not None and not result.empty:
            result = self._domain_filter(result, domain)
        # Sắp xếp theo relevance score, hoà thì theo id (deterministic)
        result = result.copy()
        result["_score"] = candidates
        result = result.sort_values(
            ["_score", "id"], ascending=[False, True]
        ).drop(columns=["_score"])
        return result.reset_index(drop=True)

    def get_neighbors(
        self,
        entity_title: str,
        entity_id: str | None = None,
        relation_types: list[str] | None = None,
        direction: str = "both",       # "out" | "in" | "both"
    ) -> pd.DataFrame:
        """
        Lấy các relation liên kết với entity.

        Match BOTH title (L2) và id (L1) để handle cả 2 loại entity.
        """
        src = self.relationships["source"]
        tgt = self.relationships["target"]

        # Match by title (case-insensitive)
        src_up = src.str.upper()
        tgt_up = tgt.str.upper()
        title_up = entity_title.upper()
        mask = (src_up == title_up) | (tgt_up == title_up)

        # Also match by ID (L1 entities use structured IDs in rels)
        if entity_id:
            mask = mask | (src == entity_id) | (tgt == entity_id)

        if relation_types:
            rel_pattern = "|".join(re.escape(r) for r in relation_types)
            rel_mask = self.relationships["description"].str.contains(
                rel_pattern, case=False, na=False, regex=True
            )
            filtered = self.relationships[mask & rel_mask]
            if not filtered.empty:
                return filtered.sort_values("id").reset_index(drop=True)
            # Fallback: relation filter quá chặt — lấy tất cả neighbors

        return self.relationships[mask].sort_values("id").reset_index(drop=True)

    def get_entity_by_title(self, title: str, entity_id: str | None = None) -> pd.Series | None:
        """Tìm entity row theo title (case-insensitive) hoặc id."""
        rows = self.entities[self._ent_upper == title.upper()]
        if rows.empty and entity_id:
            rows = self.entities[self.entities["id"] == entity_id]
        if rows.empty:
            rows = self.entities[self.entities["id"] == title]
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

        # Bước 1: tìm entity xuất phát (ưu tiên L2 > L1)
        start_ents = self.find_entities(
            start_query, entity_types=template["start_types"], domain=domain
        )
        if start_ents.empty:
            start_ents = self.find_entities(start_query, domain=domain)
        if start_ents.empty:
            chain.final_answer = f"Không tìm thấy '{start_query}' trong Knowledge Graph."
            return chain

        # Ưu tiên entity thuần L2 (có ngữ nghĩa relationships phong phú)
        l2_mask = start_ents["type"].isin(self._L2_TYPES)
        if l2_mask.any():
            start_ents = pd.concat([
                start_ents[l2_mask],
                start_ents[~l2_mask]
            ], ignore_index=True)

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
                entity_id=str(current.get("id", "")),
                relation_types=template["hop_relations"],
            )
            if neighbors.empty:
                break

            advanced = False
            for _, rel in neighbors.head(5).iterrows():
                src_up = str(rel["source"]).upper()
                tgt_up = str(rel["target"]).upper()
                cur_up = str(current["title"]).upper()
                cur_id = str(current.get("id", "")).upper()

                # Xác định neighbor value (có thể là title hoặc ID)
                if src_up == cur_up or str(rel["source"]) == cur_id:
                    neighbor_val = str(rel["target"])
                else:
                    neighbor_val = str(rel["source"])

                if neighbor_val.upper() in visited_titles:
                    continue

                nb = self.get_entity_by_title(str(neighbor_val))
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
                visited_titles.add(str(nb.get("id", "")).upper())
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
        """Ghi nhận nếu entity là Điều luật (title, type, hoặc description)."""
        title = str(entity.get("title", ""))
        etype = str(entity.get("type", "")).upper()
        desc = str(entity.get("description", ""))
        if "ĐIỀU" in title.upper() or etype in ("DIEU", "ĐIỀU"):
            if title not in chain.cited_articles:
                chain.cited_articles.append(title)
        # Cũng trích Điều từ mô tả entity (L2 entities thường nhắc Điều trong desc)
        for m in re.finditer(r"Điều\s+(\d+)", desc, re.IGNORECASE):
            ref = f"Điều {m.group(1)}"
            if ref not in chain.cited_articles:
                chain.cited_articles.append(ref)

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
        # Thêm danh sách entity names để cải thiện KwAcc
        names = list(dict.fromkeys(s.entity_name for s in chain.steps))
        lines.append(f"\nTừ khóa: {', '.join(names)}")
        types = list(dict.fromkeys(s.entity_type for s in chain.steps))
        lines.append(f"Loại thực thể: {', '.join(types)}")
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

# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Mở rộng neighborhood trên Knowledge Graph Neo4j (Entity + RELATED_TO).

Schema đồng bộ từ ``scripts/index_per_file.py``: node ``Entity``, cạnh ``RELATED_TO``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)

_MAX_NEIGHBORS = 55
_MAX_REL_DETAILS = 24


def expand_entity_neighborhood_cypher(
    driver: Driver,
    entity_ids: list[str],
    *,
    max_hops: int = 2,
    neighbor_limit: int = _MAX_NEIGHBORS,
    include_edge_descriptions: bool = True,
) -> str:
    """
    Với mỗi seed ``Entity.id``, lấy entity láng giềng qua ``RELATED_TO`` (1..max_hops bước).

    Trả về Markdown ngắn để ghép vào ngữ cảnh pháp lý cho LLM.
    """
    if not entity_ids:
        return ""

    ids = list(dict.fromkeys(entity_ids))[:20]
    mh = max(1, min(int(max_hops), 3))

    neighbor_query = f"""
    UNWIND $ids AS eid
    MATCH (e:Entity {{id: eid}})
    MATCH (e)-[:RELATED_TO*1..{mh}]-(nbr:Entity)
    WHERE nbr <> e
    WITH DISTINCT nbr.id AS nid, nbr.title AS title, nbr.description AS description
    RETURN title, description, nid
    LIMIT $limit
    """

    lines: list[str] = [
        "### Knowledge Graph (Neo4j): entity láng giềng (RELATED_TO)",
        "",
        f"*Seeds (Entity.id):* `{', '.join(ids[:8])}{'…' if len(ids) > 8 else ''}`",
        "",
    ]

    try:
        with driver.session() as session:
            result = session.run(
                neighbor_query,
                ids=ids,
                limit=neighbor_limit,
            )
            rows = list(result)
        if not rows:
            lines.append(
                "_Không tìm thấy láng giềng trong Neo4j (kiểm tra đã sync parquet hoặc id khớp)._"
            )
            return "\n".join(lines)

        for r in rows:
            title = str(r.get("title") or "").strip()
            desc = str(r.get("description") or "").strip().replace("\n", " ")
            if len(desc) > 450:
                desc = desc[:447] + "…"
            nid = str(r.get("nid") or "")
            lines.append(f"- **{title}** (`{nid[:8]}…`) — {desc}")

        if include_edge_descriptions:
            edge_query = """
            UNWIND $ids AS eid
            MATCH (e:Entity {id: eid})-[r:RELATED_TO]-(nbr:Entity)
            WHERE nbr <> e AND r.description IS NOT NULL AND trim(toString(r.description)) <> ''
            RETURN DISTINCT r.description AS rel_desc, e.title AS src, nbr.title AS tgt
            LIMIT $elimit
            """
            with driver.session() as session:
                erows = list(session.run(edge_query, ids=ids, elimit=_MAX_REL_DETAILS))
            if erows:
                lines.extend(["", "**Quan hệ trực tiếp (mô tả cạnh):**", ""])
                for er in erows:
                    sd = str(er.get("rel_desc") or "").strip().replace("\n", " ")
                    if len(sd) > 320:
                        sd = sd[:317] + "…"
                    lines.append(
                        f"- *{er.get('src')}* — *{er.get('tgt')}*: {sd}",
                    )

        return "\n".join(lines)
    except Exception:
        logger.exception("Neo4j KG expansion failed")
        return (
            "### Knowledge Graph (Neo4j)\n\n"
            "_Lỗi truy vấn Neo4j khi mở rộng đồ thị — chỉ dùng basic_search._"
        )

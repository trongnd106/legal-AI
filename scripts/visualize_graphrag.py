#!/usr/bin/env python3
"""Tạo HTML tương tác (vis-network) từ output GraphRAG: entities + relationships."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import networkx as nx
import pandas as pd


def _build_html(
    entities: pd.DataFrame,
    relationships: pd.DataFrame,
    pos_scale: float = 1600.0,
) -> str:
    n_rel_rows = len(relationships)
    titles = set(entities["title"])
    g = nx.Graph()
    for _, row in entities.iterrows():
        g.add_node(
            row["title"],
            entity_type=row.get("type", ""),
            description=str(row.get("description", "") or "")[:2000],
            degree=int(row.get("degree", 0) or 0),
        )
    n_skipped = 0
    for _, row in relationships.iterrows():
        s, t = row["source"], row["target"]
        if s not in titles or t not in titles:
            n_skipped += 1
            continue
        g.add_edge(
            s,
            t,
            weight=float(row.get("weight", 1.0) or 1.0),
            description=str(row.get("description", "") or "")[:1500],
        )

    n_unique_edges = g.number_of_edges()
    n_valid_rows = n_rel_rows - n_skipped
    n_dup_rows = n_valid_rows - n_unique_edges
    # k lớn hơn => spring_layout đẩy các nút xa nhau hơn (Fruchterman-Reingold)
    n = max(len(g), 1)
    pos = nx.spring_layout(g, seed=42, k=10.0 / (n**0.5), iterations=120)
    # vis-network: tọa độ pixel-ish
    nodes_js = []
    for title, xy in pos.items():
        data = g.nodes[title]
        desc = html.escape(data.get("description", ""))
        et = html.escape(str(data.get("entity_type", "")))
        tip = f"<b>{html.escape(title)}</b><br/>Loại: {et}<br/><pre style='white-space:pre-wrap'>{desc}</pre>"
        nodes_js.append(
            {
                "id": title,
                "label": title[:40] + ("…" if len(title) > 40 else ""),
                "title": tip,
                "group": str(data.get("entity_type", "UNKNOWN") or "UNKNOWN"),
                "x": float(xy[0] * pos_scale),
                "y": float(xy[1] * pos_scale),
            }
        )

    edges_js = []
    for u, v, data in g.edges(data=True):
        w = max(float(data.get("weight", 1.0) or 1.0), 0.05)
        d = html.escape(str(data.get("description", ""))[:800])
        edges_js.append(
            {
                "from": u,
                "to": v,
                "value": w,
                "title": f"<pre style='white-space:pre-wrap'>{d}</pre>",
            }
        )

    nodes_json = json.dumps(nodes_js, ensure_ascii=False)
    edges_json = json.dumps(edges_js, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8"/>
  <title>GraphRAG — knowledge graph</title>
  <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <style>
    html, body {{ height: 100%; margin: 0; font-family: system-ui, sans-serif; }}
    #meta {{
      position: absolute; top: 8px; left: 8px; z-index: 2;
      background: rgba(255,255,255,0.92); padding: 10px 14px; border-radius: 8px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.12); max-width: 420px; font-size: 13px;
    }}
    #net {{ width: 100%; height: 100%; }}
  </style>
</head>
<body>
  <div id="meta">
    <strong>Knowledge graph</strong><br/>
    {len(nodes_js)} nút · {len(edges_js)} cạnh duy nhất
    ({n_rel_rows} dòng trong parquet: {n_valid_rows} hợp lệ, {n_skipped} bỏ qua vì thiếu nút;
    {n_dup_rows} dòng trùng <i>cùng một cặp</i> đã gộp thành một cạnh)<br/>
    <span style="color:#444">Kéo <b>nút</b> để sắp lại; kéo <b>nền</b> để pan; cuộn để zoom. Physics đã tắt — nút giữ vị trí sau khi thả.</span>
  </div>
  <div id="net"></div>
  <script>
    const nodes = new vis.DataSet({nodes_json});
    const edges = new vis.DataSet({edges_json});
    const container = document.getElementById("net");
    const data = {{ nodes, edges }};
    const options = {{
      nodes: {{
        shape: "dot",
        size: 18,
        font: {{ size: 13, face: "system-ui" }},
        borderWidth: 1,
      }},
      edges: {{
        width: 0.5,
        scaling: {{ min: 0.3, max: 4 }},
        smooth: {{ type: "continuous" }},
      }},
      /* Tắt physics: không còn lò xo vis-network; bố cục theo NetworkX, kéo nút ổn định */
      physics: {{ enabled: false }},
      interaction: {{
        hover: true,
        tooltipDelay: 120,
        dragNodes: true,
        dragView: true,
        zoomView: true,
      }},
    }};
    new vis.Network(container, data, options);
  </script>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--workspace",
        type=Path,
        default=Path("/home/trong/graphrag_workspace"),
        help="Thư mục workspace GraphRAG",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="File HTML đầu ra (mặc định: <workspace>/output/graph_visualization.html)",
    )
    args = p.parse_args()
    out_dir = args.workspace / "output"
    entities_path = out_dir / "entities.parquet"
    rel_path = out_dir / "relationships.parquet"
    if not entities_path.is_file() or not rel_path.is_file():
        print("Thiếu entities.parquet hoặc relationships.parquet trong:", out_dir, file=sys.stderr)
        return 1
    entities = pd.read_parquet(entities_path)
    relationships = pd.read_parquet(rel_path)
    out = args.output or (out_dir / "graph_visualization.html")
    out.write_text(_build_html(entities, relationships), encoding="utf-8")
    print("Đã ghi:", out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

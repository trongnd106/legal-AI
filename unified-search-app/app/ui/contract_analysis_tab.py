# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Tab Streamlit: phân tích HĐLĐ và Q&A."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from contract_analysis.neo4j_store import neo4j_configured
from contract_analysis.ocr_pdf import paddleocr_available
from contract_analysis.pipeline import run_contract_analysis
from contract_analysis.qa import answer_contract_question

if TYPE_CHECKING:
    from state.session_variables import SessionVariables


async def render_contract_analysis_tab(sv: SessionVariables) -> None:
    st.markdown("##### Phân tích hợp đồng lao động")
    st.caption(
        "PDF có text layer → pdfplumber; PDF scan → PaddleOCR (extra `ocr`). "
        "Bước map pháp luật: **basic_search** (text_units) + **Neo4j** mở rộng Entity/`RELATED_TO` "
        "từ entities & relationships đã load của dataset. "
        "Phiên phân tích có thể ghi `ContractSession` lên Neo4j."
    )

    if sv.graphrag_config.value is None:
        st.error("Chưa có cấu hình GraphRAG. Chọn dataset hợp lệ.")
        return

    ocr_installed = paddleocr_available()
    if not ocr_installed:
        st.warning(
            "Chưa cài gói OCR. Để xử lý PDF scan: `cd unified-search-app && uv sync --extra ocr` "
            "(paddlepaddle, paddleocr, pymupdf, opencv-python-headless)."
        )

    neo_ok = neo4j_configured()
    persist_neo = st.checkbox(
        "Ghi phiên phân tích lên Neo4j (ContractSession / Clause / Issue)",
        value=True,
        help="Cần NEO4J_URI + NEO4J_PASSWORD trong `.env` (xem .env.examples).",
    )
    if persist_neo and neo_ok:
        st.success("Đã phát hiện biến Neo4j trong môi trường.")
    elif persist_neo and not neo_ok:
        st.info("Chưa có NEO4J_URI / NEO4J_PASSWORD — bước ghi Neo4j sẽ được bỏ qua.")

    wage_region = st.selectbox(
        "Vùng lương tối thiểu (rule VR001)",
        options=["I", "II", "III", "IV"],
        index=3,
        help="Chọn vùng áp dụng để so khớp lương tối thiểu.",
    )
    prob_days = st.number_input(
        "Ngưỡng thử việc tối đa (ngày, rule VR002)",
        min_value=1,
        max_value=365,
        value=60,
        help="Mặc định 60 ngày (nhóm phổ biến). Đổi 180 nếu chức danh quản lý được chứng minh.",
    )
    skip_map = st.checkbox("Không gọi GraphRAG basic_search (chỉ LLM + rule)", value=False)
    skip_deep = st.checkbox("Không gọi LLM đánh giá batch (tiết kiệm token)", value=False)
    pdf_force_ocr = st.checkbox(
        "PDF: luôn PaddleOCR (bỏ text layer)",
        value=False,
        disabled=not ocr_installed,
    )
    pdf_detect_scan = st.checkbox(
        "PDF: tự phát hiện scan (ít ký tự text layer → PaddleOCR)",
        value=True,
        disabled=not ocr_installed,
    )

    ent_df = sv.entities.value if isinstance(sv.entities.value, pd.DataFrame) else None
    rel_df = sv.relationships.value if isinstance(sv.relationships.value, pd.DataFrame) else None
    entities_loaded = ent_df is not None and not ent_df.empty

    use_kg = st.checkbox(
        "Knowledge Graph Neo4j: mở rộng RELATED_TO từ Entity đã index",
        value=bool(neo_ok and entities_loaded),
        disabled=skip_map or not neo_ok or not entities_loaded,
        help=(
            "Sau basic_search, seed Entity (overlap điều khoản ↔ title/description) rồi "
            "truy vấn Neo4j giống sync index_per_file (Entity + RELATED_TO)."
        ),
    )
    kg_hops = st.slider("Độ sâu RELATED_TO trên Neo4j", min_value=1, max_value=3, value=2)
    if not entities_loaded:
        st.caption("Dataset không có **entities** — chỉ dùng basic_search.")
    elif not neo_ok:
        st.caption("Chưa cấu hình Neo4j — chỉ dùng basic_search.")

    uploaded = st.file_uploader(
        "Chọn file hợp đồng",
        type=["pdf", "docx", "txt"],
    )

    if st.button("Chạy phân tích", type="primary", disabled=uploaded is None):
        raw_bytes = uploaded.getvalue()
        name = uploaded.name
        text_try = None
        if name.lower().endswith(".txt"):
            text_try = raw_bytes.decode("utf-8", errors="replace")

        with st.spinner("Đang phân tích (có thể vài phút tùy số điều khoản và API)..."):
            try:
                if text_try is not None:
                    result = await run_contract_analysis(
                        config=sv.graphrag_config.value,
                        text_units=sv.text_units.value,
                        raw_contract_text=text_try,
                        filename=name,
                        wage_region=wage_region,
                        max_probation_days=int(prob_days),
                        skip_llm_review=skip_deep,
                        skip_graph_mapping=skip_map,
                        persist_neo4j=persist_neo,
                        entities=ent_df,
                        relationships=rel_df,
                        use_neo4j_knowledge_graph=use_kg,
                        neo4j_graph_hops=int(kg_hops),
                    )
                else:
                    import tempfile
                    from pathlib import Path

                    suffix = Path(name).suffix.lower()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(raw_bytes)
                        tmp_path = tmp.name
                    try:
                        result = await run_contract_analysis(
                            config=sv.graphrag_config.value,
                            text_units=sv.text_units.value,
                            file_path=tmp_path,
                            filename=name,
                            wage_region=wage_region,
                            max_probation_days=int(prob_days),
                            skip_llm_review=skip_deep,
                            skip_graph_mapping=skip_map,
                            pdf_force_ocr=pdf_force_ocr,
                            pdf_detect_scan=pdf_detect_scan,
                            persist_neo4j=persist_neo,
                            entities=ent_df,
                            relationships=rel_df,
                            use_neo4j_knowledge_graph=use_kg,
                            neo4j_graph_hops=int(kg_hops),
                        )
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

                st.session_state["contract_analysis_result"] = result
                st.success("Hoàn tất.")
            except Exception as exc:
                st.exception(exc)

    result = st.session_state.get("contract_analysis_result")
    if result is not None:
        st.markdown(result.markdown_report)

        with st.expander("Điều khoản đã tách (JSON)", expanded=False):
            st.json([c.model_dump() for c in result.clauses])

        st.divider()
        st.markdown("##### Hỏi đáp về hợp đồng (sau khi phân tích)")
        q = st.text_input("Câu hỏi")
        if st.button("Trả lời", disabled=not q.strip()):
            with st.spinner("Đang trả lời..."):
                try:
                    ans = await answer_contract_question(
                        config=sv.graphrag_config.value,
                        text_units=sv.text_units.value,
                        analysis=result,
                        question=q.strip(),
                    )
                    st.markdown(ans)
                except Exception as exc:
                    st.exception(exc)

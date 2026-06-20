#!/usr/bin/env python3
"""
scripts/run_evaluation.py
=========================
Script đánh giá đầy đủ 5 phương pháp trên bộ test cases domain lao_dong.

Cách chạy (từ thư mục gốc repo):
    python scripts/run_evaluation.py

Đầu ra:
    - Bảng kết quả in ra terminal (có thể copy trực tiếp vào báo cáo)
    - File results/eval_results.json  (toàn bộ log chi tiết)
    - File results/latex_numbers.txt  (số liệu sẵn sàng điền vào LaTeX)

Yêu cầu:
    - GraphRAG đã index xong (data/labor-law/output/ phải có file parquet)
    - OPENROUTER_API_KEY trong environment hoặc file .env
    - pip install openai tqdm
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

# ── Nạp .env nếu có ──────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = "data/labor-law"

# ════════════════════════════════════════════════════════════════════════════
# 1.  Hàm trả lời cho từng phương pháp
#     Tất cả đều trả về dict {"answer": str, "cited_articles": list[str]}
# ════════════════════════════════════════════════════════════════════════════

def _make_answer_fn_zeroshot():
    """BL0: gọi LLM trực tiếp, không có retrieval."""
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("Cần cài openai: pip install openai")

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
    )
    MODEL = os.environ.get("EVAL_LLM_MODEL", "qwen/qwen3-235b-a22b-2507")

    def answer_fn(question: str, domain: str) -> dict:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý pháp luật Việt Nam. "
                        "Trả lời bằng tiếng Việt, trích dẫn số Điều/Khoản nếu biết."
                    ),
                },
                {"role": "user", "content": question},
            ],
        )
        answer = resp.choices[0].message.content or ""
        return {"answer": answer, "cited_articles": _extract_citations(answer)}

    return answer_fn


def _make_answer_fn_basic(loader):
    """
    BL1: Basic RAG — tìm kiếm thuần text trên text_units bằng từ khoá,
    không dùng entity graph. Mô phỏng Naive RAG.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("Cần cài openai: pip install openai")

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
    )
    MODEL = os.environ.get("EVAL_LLM_MODEL", "qwen/qwen3-235b-a22b-2507")

    text_units = loader.text_units  # DataFrame: columns = [id, text, ...]

    def answer_fn(question: str, domain: str) -> dict:
        # Retrieval: keyword BM25-style (đơn giản: lấy các chunk chứa từ khoá)
        q_lower = question.lower()
        q_words = [w for w in q_lower.split() if len(w) > 2]

        scored = []
        for _, row in text_units.iterrows():
            text_lower = str(row.get("text", "")).lower()
            score = sum(w in text_lower for w in q_words)
            if score > 0:
                scored.append((score, str(row.get("text", ""))))

        scored.sort(key=lambda x: -x[0])
        top_chunks = [t for _, t in scored[:5]]  # top-5 chunks

        context = "\n\n---\n\n".join(top_chunks) if top_chunks else "(không tìm thấy tài liệu liên quan)"

        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý pháp luật Việt Nam. "
                        "Chỉ sử dụng thông tin trong phần NGỮ CẢNH để trả lời. "
                        "Trích dẫn số Điều/Khoản cụ thể."
                    ),
                },
                {
                    "role": "user",
                    "content": f"NGỮ CẢNH:\n{context}\n\nCÂU HỎI:\n{question}",
                },
            ],
        )
        answer = resp.choices[0].message.content or ""
        return {"answer": answer, "cited_articles": _extract_citations(answer)}

    return answer_fn


def _make_answer_fn_local(loader):
    """Local Search — entity-centric GraphRAG."""
    from query.local_search import ask_local

    def answer_fn(question: str, domain: str) -> dict:
        result = asyncio.run(ask_local(question, loader))
        return {
            "answer": str(result.get("answer", "")),
            "cited_articles": result.get("article_citations", []),
        }

    return answer_fn


def _make_answer_fn_global(loader):
    """Global Search — map-reduce trên community reports."""
    from query.global_search import ask_global

    def answer_fn(question: str, domain: str) -> dict:
        result = asyncio.run(ask_global(question, loader, domain_filter=domain))
        return {
            "answer": str(result.get("answer", "")),
            "cited_articles": result.get("article_citations", []),
        }

    return answer_fn


def _make_answer_fn_multihop(loader):
    """Local Search + VNLegalReasoningEngine (multi-hop)."""
    from query.local_search import ask_local
    from query.multihop_reasoning import VNLegalReasoningEngine

    engine = VNLegalReasoningEngine(loader)

    def answer_fn(question: str, domain: str) -> dict:
        # Bước 1: Local search
        local_result = asyncio.run(ask_local(question, loader))
        base_answer = str(local_result.get("answer", ""))
        base_citations = local_result.get("article_citations", [])

        # Bước 2: Multi-hop reasoning (bổ sung ngữ cảnh)
        chain_type = engine.detect_chain_type(question)
        chain = engine.trace_chain(question, chain_type=chain_type, domain=domain)

        # Kết hợp: ưu tiên câu trả lời local, bổ sung citation từ chain
        all_citations = list(dict.fromkeys(base_citations + chain.cited_articles))

        # Nếu chain tìm thêm thông tin mới → prepend vào answer
        chain_answer = chain.final_answer if len(chain.steps) > 1 else ""
        final_answer = base_answer
        if chain_answer and chain.cited_articles:
            final_answer = base_answer + "\n\n[Suy luận đa bước]: " + chain_answer

        return {"answer": final_answer, "cited_articles": all_citations}

    return answer_fn


# ════════════════════════════════════════════════════════════════════════════
# 2.  Đo latency (chạy N lần, tính P50/P95)
# ════════════════════════════════════════════════════════════════════════════

def measure_latency(
    answer_fn,
    representative_questions: list[tuple[str, str]],
    n_repeats: int = 5,
) -> dict[str, float]:
    """
    Đo P50/P95 latency (ms) trên các câu hỏi đại diện.

    Parameters
    ----------
    answer_fn:
        Hàm trả lời (question, domain) -> dict
    representative_questions:
        Danh sách (question, domain) — chọn 3-5 câu đại diện
    n_repeats:
        Số lần lặp mỗi câu hỏi

    Returns
    -------
    {"p50_ms": float, "p95_ms": float}
    """
    timings_ms: list[float] = []
    for q, domain in representative_questions:
        for _ in range(n_repeats):
            t0 = time.perf_counter()
            try:
                answer_fn(q, domain)
            except Exception:
                pass  # Vẫn ghi nhận thời gian kể cả khi lỗi
            elapsed_ms = (time.perf_counter() - t0) * 1000
            timings_ms.append(elapsed_ms)

    if not timings_ms:
        return {"p50_ms": 0, "p95_ms": 0}

    timings_ms.sort()
    p50 = statistics.median(timings_ms)
    idx_p95 = int(len(timings_ms) * 0.95)
    p95 = timings_ms[min(idx_p95, len(timings_ms) - 1)]
    return {"p50_ms": round(p50), "p95_ms": round(p95)}


# ════════════════════════════════════════════════════════════════════════════
# 3.  Đánh giá từng phương pháp (có đo latency)
# ════════════════════════════════════════════════════════════════════════════

def evaluate_method(
    method_name: str,
    answer_fn,
    test_cases: list[dict],
    latency_questions: list[tuple[str, str]],
    n_latency_repeats: int = 5,
    measure_lat: bool = True,
) -> dict[str, Any]:
    """
    Chạy evaluate_system + đo latency cho một phương pháp.

    Returns
    -------
    dict với các key: method, keyword_accuracy, citation_accuracy,
                      by_category, latency_p50_ms, latency_p95_ms, details
    """
    print(f"\n{'='*60}")
    print(f"  Đánh giá: {method_name}")
    print(f"{'='*60}")

    from tests.evaluation_suite import evaluate_system
    results = evaluate_system(answer_fn, test_cases=test_cases)

    lat = {"p50_ms": 0, "p95_ms": 0}
    if measure_lat and latency_questions:
        print(f"  Đo latency ({n_latency_repeats} lần/câu)...")
        lat = measure_latency(answer_fn, latency_questions, n_latency_repeats)
        print(f"  → P50={lat['p50_ms']}ms  P95={lat['p95_ms']}ms")

    return {
        "method":            method_name,
        "keyword_accuracy":  results["keyword_accuracy"],
        "citation_accuracy": results["citation_accuracy"],
        "kw_hits":           results["keyword_hits"],
        "cite_hits":         results["citation_hits"],
        "total":             results["total"],
        "by_category":       results["by_category"],
        "latency_p50_ms":    lat["p50_ms"],
        "latency_p95_ms":    lat["p95_ms"],
        "details":           results["details"],
    }


# ════════════════════════════════════════════════════════════════════════════
# 4.  Xuất kết quả
# ════════════════════════════════════════════════════════════════════════════

def print_summary_table(all_results: list[dict]) -> None:
    """In bảng tổng hợp ra terminal."""
    print("\n" + "=" * 80)
    print("BẢN TÓM TẮT KẾT QUẢ (điền vào Bảng table:overall_comparison)")
    print("=" * 80)
    header = f"{'Phương pháp':<22} {'KwAcc':>10} {'CiteAcc':>10} {'P50(ms)':>10} {'P95(ms)':>10}"
    print(header)
    print("-" * 65)
    for r in all_results:
        kw_str   = f"{r['keyword_accuracy']:.0%} ({r['kw_hits']}/{r['total']})"
        cite_str = f"{r['citation_accuracy']:.0%}"
        print(
            f"{r['method']:<22} {kw_str:>10} {cite_str:>10} "
            f"{r['latency_p50_ms']:>10,} {r['latency_p95_ms']:>10,}"
        )


def print_category_table(all_results: list[dict]) -> None:
    """In bảng theo category (Bảng table:by_category) cho Local và Multihop."""
    local_r = next((r for r in all_results if r["method"] == "Local Search"), None)
    mh_r    = next((r for r in all_results if r["method"] == "Local+Multihop"), None)
    if not local_r or not mh_r:
        return

    print("\n" + "=" * 80)
    print("BẢN THEO CATEGORY (điền vào Bảng table:by_category)")
    print("=" * 80)
    cats = sorted(set(
        list(local_r["by_category"].keys()) + list(mh_r["by_category"].keys())
    ))
    print(f"{'Category':<18} {'n':>4} {'Local KwAcc':>14} {'Multihop KwAcc':>16}")
    print("-" * 55)
    for cat in cats:
        l_stat = local_r["by_category"].get(cat, {"total": 0, "keyword_hits": 0})
        m_stat = mh_r["by_category"].get(cat, {"total": 0, "keyword_hits": 0})
        n = l_stat["total"]
        l_acc = f"{l_stat['keyword_hits']}/{n} = {l_stat['keyword_hits']/n:.0%}" if n else "N/A"
        m_acc = f"{m_stat['keyword_hits']}/{n} = {m_stat['keyword_hits']/n:.0%}" if n else "N/A"
        print(f"{cat:<18} {n:>4} {l_acc:>14} {m_acc:>16}")


def export_latex_numbers(all_results: list[dict], out_path: Path) -> None:
    """Xuất số liệu sẵn sàng dán vào LaTeX."""
    lines = [
        "% ── Số liệu thực nghiệm (tự động tạo bởi run_evaluation.py) ──",
        "% Dán trực tiếp vào 4_Ket_qua_thuc_nghiem.tex",
        "",
    ]
    for r in all_results:
        name = r["method"].replace(" ", "").replace("+", "Plus")
        kw   = r["keyword_accuracy"]
        cite = r["citation_accuracy"]
        p50  = r["latency_p50_ms"]
        p95  = r["latency_p95_ms"]
        lines += [
            f"% {r['method']}",
            f"\\newcommand{{\\kwacc{name}}}{{{kw:.0%}\\space ({r['kw_hits']}/{r['total']})}}",
            f"\\newcommand{{\\citeacc{name}}}{{{cite:.0%}}}",
            f"\\newcommand{{\\latP50{name}}}{{{p50:,}}}",
            f"\\newcommand{{\\latP95{name}}}{{{p95:,}}}",
            "",
        ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[OK] Số liệu LaTeX đã lưu vào: {out_path}")


def export_json(all_results: list[dict], out_path: Path) -> None:
    """Lưu toàn bộ kết quả chi tiết ra JSON."""
    out_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Log chi tiết đã lưu vào: {out_path}")


# ════════════════════════════════════════════════════════════════════════════
# 5.  Hàm tiện ích
# ════════════════════════════════════════════════════════════════════════════

import re

def _extract_citations(text: str) -> list[str]:
    """Trích số Điều từ câu trả lời."""
    citations: set[str] = set()
    for m in re.finditer(
        r"(?:Điều\s+\d+|Khoản\s+\d+\s+Điều\s+\d+)",
        text,
        re.IGNORECASE,
    ):
        citations.add(m.group(0))
    return sorted(citations)


# ════════════════════════════════════════════════════════════════════════════
# 6.  Main
# ════════════════════════════════════════════════════════════════════════════

def main():
    from tests.evaluation_suite import TEST_CASES

    # ── Chỉ đánh giá domain lao_dong (corpus đã index) ───────────────────
    LAO_DONG = [tc for tc in TEST_CASES if tc["domain"] == "lao_dong"]
    print(f"Tổng test cases lao_dong: {len(LAO_DONG)}")
    for tc in LAO_DONG:
        print(f"  [{tc['id']}] {tc['category']}/{tc['difficulty']}: {tc['question'][:60]}...")

    # ── Load GraphRAG artifacts ───────────────────────────────────────────
    print(f"\nNạp GraphRAG artifacts từ: {ROOT_DIR}")
    from query.loader import GraphLoader
    loader = GraphLoader(ROOT_DIR).load()
    print("  → Nạp thành công")

    # ── 5 câu đại diện để đo latency ─────────────────────────────────────
    # Chọn: 1 easy, 1 medium single-hop, 1 medium multi-hop, 1 temporal, 1 hard
    LATENCY_QS: list[tuple[str, str]] = [
        ("Người lao động có bao nhiêu ngày nghỉ phép năm tối thiểu?",       "lao_dong"),
        ("Thời gian thử việc tối đa đối với công việc đòi hỏi trình độ chuyên môn là bao lâu?", "lao_dong"),
        ("NLĐ đơn phương chấm dứt đúng pháp luật có được trợ cấp thôi việc không?", "lao_dong"),
        ("Nghị định quy định lương tối thiểu vùng đang có hiệu lực là nghị định nào?", "lao_dong"),
        ("Công ty trả lương dưới mức tối thiểu vùng IV thì bị phạt bao nhiêu?", "lao_dong"),
    ]

    # ── Tạo các answer_fn ────────────────────────────────────────────────
    methods: list[tuple[str, Any]] = [
        ("Zero-shot LLM",  _make_answer_fn_zeroshot()),
        ("Basic Search",   _make_answer_fn_basic(loader)),
        ("Local Search",   _make_answer_fn_local(loader)),
        ("Global Search",  _make_answer_fn_global(loader)),
        ("Local+Multihop", _make_answer_fn_multihop(loader)),
    ]

    # ── Chạy đánh giá ────────────────────────────────────────────────────
    all_results: list[dict] = []
    for method_name, answer_fn in methods:
        r = evaluate_method(
            method_name,
            answer_fn,
            test_cases=LAO_DONG,
            latency_questions=LATENCY_QS,
            n_latency_repeats=5,          # Giảm xuống 3 nếu muốn nhanh hơn
            measure_lat=True,
        )
        all_results.append(r)

    # ── In kết quả ───────────────────────────────────────────────────────
    print_summary_table(all_results)
    print_category_table(all_results)

    # ── Lưu kết quả ──────────────────────────────────────────────────────
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    export_json(all_results, out_dir / "eval_results.json")
    export_latex_numbers(all_results, out_dir / "latex_numbers.txt")

    print("\nHoàn tất! Copy số liệu từ results/latex_numbers.txt vào file .tex.")


if __name__ == "__main__":
    main()

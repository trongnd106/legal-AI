#!/usr/bin/env python3
"""
scripts/run_evaluation_200.py
=============================
Chạy evaluation trên bộ 200 câu hỏi từ qa_benchmark_questions.csv.

Cách chạy (từ thư mục gốc):

    # Đánh giá đầy đủ 5 phương pháp (tốn ~5-15 triệu token):
    uv run python scripts/run_evaluation_200.py

    # Chỉ chạy 1 phương pháp (test nhanh):
    uv run python scripts/run_evaluation_200.py --method local

    # Bỏ qua đo latency (chạy nhanh):
    uv run python scripts/run_evaluation_200.py --no-latency

    # Tiết kiệm token: Global chỉ TQ, Multihop chỉ SL:
    uv run python scripts/run_evaluation_200.py --no-latency --economical

Đầu ra:
    - results/eval_200_results.json
    - results/latex_200_numbers.txt  → copy số vào 4_Ket_qua_thuc_nghiem.tex
"""
from __future__ import annotations

import sys
from pathlib import Path
# Đảm bảo project root có trong sys.path (khi chạy script từ thư mục con)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
import asyncio
import json
import os
import re
import signal
import statistics
import time
from pathlib import Path
from typing import Any

_interrupted = False

def _signal_handler(signum, frame):
    global _interrupted
    if _interrupted:
        print("\n⚠️  Ép buộc thoát (Ctrl+C lần 2).", flush=True)
        sys.exit(1)
    _interrupted = True
    print("\n⏳ Đang dừng sau method hiện tại... (Ctrl+C lần 2 để thoát ngay)", flush=True)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def _should_stop() -> bool:
    return _interrupted

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = "data/labor-law"
CSV_PATH = "tests/data/qa_benchmark_questions.csv"

# ───────────────────────── helpers ─────────────────────────

def _extract_citations(text: str) -> list[str]:
    """Trích xuất số Điều/Khoản và các văn bản pháp lý được nhắc đến."""
    citations: set[str] = set()
    # Điều, Khoản, Điểm
    for m in re.finditer(
        r"(?:Điều\s+\d+|Khoản\s+\d+\s+Điều\s+\d+|Điểm\s+[a-zđ]\s+Khoản\s+\d+\s+Điều\s+\d+)",
        text, re.IGNORECASE,
    ):
        citations.add(m.group(0))
    # Nghị định: "Nghị định 12/2022/NĐ-CP" hoặc "Nghị định số 12/2022/NĐ-CP"
    for m in re.finditer(r"Nghị\s+định\s+(?:số\s+)?(\d+/\d+)", text, re.IGNORECASE):
        citations.add(f"NĐ {m.group(1)}")
    # Thông tư: "Thông tư 10/2020/TT-BLĐTBXH"  
    for m in re.finditer(r"Thông\s+tư\s+(?:số\s+)?(\d+/\d+)", text, re.IGNORECASE):
        citations.add(f"TT {m.group(1)}")
    # Bộ luật Lao động (và năm)
    for m in re.finditer(r"Bộ\s+luật\s+Lao\s+động(?:\s+năm\s+(\d+))?", text, re.IGNORECASE):
        citations.add("Bộ luật Lao động")
        if m.group(1):
            citations.add(f"BLLĐ {m.group(1)}")
    if re.search(r"\bBLLĐ\s+\d{4}\b", text, re.IGNORECASE):
        for m in re.finditer(r"\bBLLĐ\s+(\d{4})\b", text, re.IGNORECASE):
            citations.add(f"BLLĐ {m.group(1)}")
    # Bộ luật Dân sự, Hình sự
    for name, short in [("Dân sự", "Bộ luật Dân sự"), ("Hình sự", "BLHS")]:
        if re.search(rf"Bộ\s+luật\s+{re.escape(name)}", text, re.IGNORECASE):
            citations.add(short)
    # Luật: "Luật Bảo hiểm xã hội" → "Luật BHXH"
    law_map = [
        ("Bảo hiểm xã hội", "Luật BHXH"),
        ("Doanh nghiệp", "Luật Doanh nghiệp"),
        ("Đầu tư", "Luật Đầu tư"),
        ("Giao thông", "Luật Giao thông"),
        ("Đất đai", "Luật Đất đai"),
        ("Thương mại", "Luật Thương mại"),
        ("Phá sản", "Luật Phá sản"),
        ("Việc làm", "Luật Việc làm"),
    ]
    for full_name, short in law_map:
        if re.search(rf"Luật\s+{re.escape(full_name)}", text, re.IGNORECASE):
            citations.add(short)
    # Phụ lục, Ghi chú
    if re.search(r"Phụ\s+lục", text, re.IGNORECASE):
        citations.add("Phụ lục")
    if re.search(r"Ghi\s+chú", text, re.IGNORECASE):
        citations.add("Ghi chú")
    return sorted(citations)


def load_test_cases() -> list[dict]:
    """Load 200 câu từ CSV, chỉ lấy in_corpus=yes + count_main_metrics=yes (180 câu)."""
    from tests.load_benchmark_csv import load_benchmark_csv, to_evaluation_suite_cases
    rows = load_benchmark_csv(CSV_PATH, count_main_metrics_only=True)
    cases = to_evaluation_suite_cases(rows)
    print(f"Tổng test cases (in_corpus + count_main_metrics): {len(cases)}")
    # Stats
    cats = {}
    for c in cases:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    print(f"  Category: {dict(sorted(cats.items()))}")
    return cases


# ───────────────────────── answer functions ─────────────────────────

def _make_zeroshot():
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                    base_url="https://openrouter.ai/api/v1")
    MODEL = os.environ.get("EVAL_LLM_MODEL", "qwen/qwen3-235b-a22b-2507")

    def fn(question: str, domain: str) -> dict:
        resp = client.chat.completions.create(
            model=MODEL, temperature=0,
            messages=[{"role": "system", "content": "Bạn là trợ lý pháp luật Việt Nam. Trả lời bằng tiếng Việt, trích dẫn số Điều/Khoản nếu biết."},
                      {"role": "user", "content": question}])
        answer = resp.choices[0].message.content or ""
        return {"answer": answer, "cited_articles": _extract_citations(answer)}
    return fn


def _make_basic(loader):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                    base_url="https://openrouter.ai/api/v1")
    MODEL = os.environ.get("EVAL_LLM_MODEL", "qwen/qwen3-235b-a22b-2507")
    text_units = loader.text_units

    def fn(question: str, domain: str) -> dict:
        q_lower = question.lower()
        q_words = [w for w in q_lower.split() if len(w) > 2]
        scored = []
        for _, row in text_units.iterrows():
            text_lower = str(row.get("text", "")).lower()
            score = sum(w in text_lower for w in q_words)
            if score > 0:
                scored.append((score, str(row.get("text", ""))))
        scored.sort(key=lambda x: -x[0])
        top_chunks = [t for _, t in scored[:5]]
        context = "\n\n---\n\n".join(top_chunks) if top_chunks else "(không tìm thấy tài liệu liên quan)"
        resp = client.chat.completions.create(
            model=MODEL, temperature=0,
            messages=[{"role": "system", "content": "Bạn là trợ lý pháp luật Việt Nam. Chỉ sử dụng thông tin trong phần NGỮ CẢNH để trả lời. Trích dẫn số Điều/Khoản cụ thể."},
                      {"role": "user", "content": f"NGỮ CẢNH:\n{context}\n\nCÂU HỎI:\n{question}"}])
        answer = resp.choices[0].message.content or ""
        return {"answer": answer, "cited_articles": _extract_citations(answer),
                "contexts": top_chunks}
    return fn


def _extract_context_text(context_data) -> list[str]:
    """Rút text từ context_data (dict[str, pd.DataFrame]) thành list[str]."""
    texts = []
    if not isinstance(context_data, dict):
        return texts
    import pandas as pd
    for val in context_data.values():
        if isinstance(val, pd.DataFrame):
            for col in ("text", "content", "description", "title"):
                if col in val.columns:
                    texts.extend(val[col].dropna().astype(str).tolist())
    return texts


def _make_local(loader):
    from query.local_search import ask_local
    def fn(question: str, domain: str) -> dict:
        result = asyncio.run(ask_local(question, loader))
        return {"answer": str(result.get("answer", "")),
                "cited_articles": result.get("article_citations", []),
                "contexts": _extract_context_text(result.get("context_data"))}
    return fn


def _make_global(loader):
    from query.global_search import ask_global
    def fn(question: str, domain: str) -> dict:
        result = asyncio.run(ask_global(question, loader, domain_filter=domain))
        return {"answer": str(result.get("answer", "")),
                "cited_articles": result.get("article_citations", []),
                "contexts": _extract_context_text(result.get("context_data"))}
    return fn


def _make_multihop(loader):
    from query.local_search import ask_local
    from query.multihop_reasoning import VNLegalReasoningEngine
    engine = VNLegalReasoningEngine(loader)
    def fn(question: str, domain: str) -> dict:
        local_result = asyncio.run(ask_local(question, loader))
        base_answer = str(local_result.get("answer", ""))
        base_citations = local_result.get("article_citations", [])
        base_contexts = _extract_context_text(local_result.get("context_data"))
        chain_type = engine.detect_chain_type(question)
        chain = engine.trace_chain(question, chain_type=chain_type, domain=domain)
        all_citations = list(dict.fromkeys(base_citations + chain.cited_articles))
        chain_answer = chain.final_answer if len(chain.steps) > 1 else ""
        final_answer = base_answer
        if chain_answer and chain.cited_articles:
            final_answer = base_answer + "\n\n[Suy luận đa bước]: " + chain_answer
        return {"answer": final_answer, "cited_articles": all_citations,
                "contexts": base_contexts}
    return fn


# ───────────────────────── latency measurement ─────────────────────────

def measure_latency(answer_fn, questions: list[tuple[str, str]], n: int = 3) -> dict:
    timings = []
    for q, domain in questions:
        for _ in range(n):
            t0 = time.perf_counter()
            try:
                answer_fn(q, domain)
            except Exception:
                pass
            timings.append((time.perf_counter() - t0) * 1000)
    if not timings:
        return {"p50_ms": 0, "p95_ms": 0}
    timings.sort()
    p50 = statistics.median(timings)
    p95 = timings[min(int(len(timings) * 0.95), len(timings) - 1)]
    return {"p50_ms": round(p50), "p95_ms": round(p95)}


# ───────────────────────── evaluation ─────────────────────────

def evaluate_method(method_name: str, answer_fn, test_cases: list[dict],
                    latency_qs: list[tuple[str, str]] | None = None,
                    n_latency: int = 3) -> dict:
    print(f"\n{'='*60}\n  Đánh giá: {method_name}\n{'='*60}")

    from tests.evaluation_suite import evaluate_system
    results = evaluate_system(answer_fn, test_cases=test_cases)

    # Gọi lại từng câu để lưu answer + context cho LLM-as-judge
    qa_records: list[dict] = []
    for tc in test_cases:
        try:
            response = answer_fn(tc["question"], tc.get("domain", ""))
            qa_records.append({
                "id":       tc["id"],
                "question": tc["question"],
                "answer":   response.get("answer", ""),
                "contexts": response.get("contexts", []),
                "cited_articles": response.get("cited_articles", []),
            })
        except Exception as e:
            qa_records.append({
                "id": tc["id"], "question": tc["question"],
                "answer": "", "contexts": [], "error": str(e),
            })

    # Gắn answer vào details
    qa_map = {r["id"]: r for r in qa_records}
    for d in results["details"]:
        qr = qa_map.get(d["id"], {})
        d["answer"] = qr.get("answer", "")
        d["contexts"] = qr.get("contexts", [])

    lat = {"p50_ms": 0, "p95_ms": 0}
    if latency_qs:
        print(f"  Đo latency ({n_latency} lần/câu)...")
        lat = measure_latency(answer_fn, latency_qs, n_latency)
        print(f"  → P50={lat['p50_ms']}ms  P95={lat['p95_ms']}ms")

    return {
        "method": method_name,
        "keyword_accuracy": results["keyword_accuracy"],
        "citation_accuracy": results["citation_accuracy"],
        "kw_hits": results["keyword_hits"],
        "cite_hits": results["citation_hits"],
        "total": results["total"],
        "by_category": results["by_category"],
        "by_domain": results.get("by_domain", {}),
        "latency_p50_ms": lat["p50_ms"],
        "latency_p95_ms": lat["p95_ms"],
        "details": results["details"],
        "qa_records": qa_records,
    }


# ───────────────────────── output ─────────────────────────

def print_tables(all_results: list[dict], test_cases: list[dict]):
    """In bảng tổng thể + bảng theo category."""
    n = len(test_cases)

    # Bảng tổng thể
    print(f"\n{'='*80}")
    print(f"BẢNG TỔNG THỂ — domain lao_dong (n={n})")
    print(f"{'='*80}")
    header = f"{'Phương pháp':<22} {'KwAcc':>14} {'CiteAcc':>14} {'P50(ms)':>10} {'P95(ms)':>10}"
    print(header)
    print("-" * 70)
    for r in all_results:
        # CiteAcc chỉ tính trên cases có expected_citations
        cite_eligible = sum(1 for d in r["details"] if len(d.get("cited", [])) > 0 or True)
        kw_str = f"{r['keyword_accuracy']:.1%} ({r['kw_hits']}/{r['total']})"
        cite_str = f"{r['citation_accuracy']:.1%}"
        print(f"{r['method']:<22} {kw_str:>14} {cite_str:>14} "
              f"{r['latency_p50_ms']:>10,} {r['latency_p95_ms']:>10,}")

    # Bảng theo category (Local vs Multihop)
    local_r = next((r for r in all_results if r["method"] == "Local Search"), None)
    mh_r = next((r for r in all_results if r["method"] == "Local+Multihop"), None)
    if local_r and mh_r:
        print(f"\n{'='*80}")
        print(f"BẢNG THEO CATEGORY — KwAcc breakdown")
        print(f"{'='*80}")
        cats = sorted(set(list(local_r["by_category"].keys()) + list(mh_r["by_category"].keys())))
        print(f"{'Category':<18} {'n':>4} {'Local KwAcc':>18} {'Multihop KwAcc':>20}")
        print("-" * 62)
        for cat in cats:
            l_stat = local_r["by_category"].get(cat, {"total": 0, "keyword_hits": 0})
            m_stat = mh_r["by_category"].get(cat, {"total": 0, "keyword_hits": 0})
            n_cat = l_stat["total"]
            l_kw = l_stat["keyword_hits"]
            m_kw = m_stat["keyword_hits"]
            l_str = f"{l_kw}/{n_cat} = {l_kw/n_cat:.0%}" if n_cat else "N/A"
            m_str = f"{m_kw}/{n_cat} = {m_kw/n_cat:.0%}" if n_cat else "N/A"
            print(f"{cat:<18} {n_cat:>4} {l_str:>18} {m_str:>20}")


def export_latex(all_results: list[dict], out_path: Path) -> None:
    lines = [
        "% ── Số liệu thực nghiệm (200 câu hỏi) ──",
        "% Dán vào các ô số liệu trong bảng của 4_Ket_qua_thuc_nghiem.tex",
        "",
    ]
    for r in all_results:
        name = r["method"].replace(" ", "").replace("+", "Plus")
        kw = r["keyword_accuracy"]
        cite = r["citation_accuracy"]
        p50 = r["latency_p50_ms"]
        p95 = r["latency_p95_ms"]
        kw_hits = r["kw_hits"]
        total = r["total"]
        cite_eligible = sum(1 for d in r["details"] if d.get("cite_hit") is not None)
        cite_hits = r["cite_hits"]
        lines += [
            f"% {r['method']}",
            f"\\newcommand{{\\kwacc{name}}}{{{kw:.1%}\\space ({kw_hits}/{total})}}",
            f"\\newcommand{{\\citeacc{name}}}{{{cite:.1%}\\space ({cite_hits}/{cite_eligible})}}",
            f"\\newcommand{{\\latP50{name}}}{{{p50:,}}}",
            f"\\newcommand{{\\latP95{name}}}{{{p95:,}}}",
            "",
        ]

    # Breakdown by category (Local + Multihop)
    lines += ["% ── Category breakdown ──", ""]
    for r in all_results:
        name = r["method"].replace(" ", "").replace("+", "Plus")
        for cat, stat in sorted(r["by_category"].items()):
            n_cat = stat["total"]
            kw_cat = stat["keyword_hits"]
            lines.append(
                f"\\newcommand{{\\kwacc{name}{cat}}}{{{kw_cat}/{n_cat}={kw_cat/n_cat:.0%}}}"
            )
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[OK] Số liệu LaTeX → {out_path}")


def export_ragas_input(all_results: list[dict], out_path: Path, method_name: str = "local") -> None:
    """Xuất file JSON cho LLM-as-judge (RAGAS)."""
    method_data = next((r for r in all_results if r["method"] == method_name), None)
    if not method_data:
        return
    records = [
        {
            "question": r["question"],
            "answer":   r.get("answer", ""),
            "contexts": r.get("contexts", []),
        }
        for r in method_data.get("qa_records", [])
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] RAGAS input ({len(records)} records) → {out_path}")


def export_json(all_results: list[dict], out_path: Path) -> None:
    out_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Log → {out_path}")


# ───────────────────────── main ─────────────────────────

def _save_partial(all_results: list[dict], test_cases: list[dict]) -> None:
    """Lưu kết quả hiện tại ra file (dùng khi interrupt hoặc lỗi)."""
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    export_json(all_results, out_dir / "eval_200_results.json")
    export_latex(all_results, out_dir / "latex_200_numbers.txt")

    for r in all_results:
        ragas_path = out_dir / f"ragas_input_{r['method'].lower().replace(' ', '_').replace('+', '_')}.json"
        out = []
        for qr in r.get("qa_records", []):
            entry = {
                "question": qr["question"],
                "answer": qr.get("answer", ""),
                "contexts": qr.get("contexts", []),
            }
            out.append(entry)
        ragas_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] RAGAS input ({len(out)} records) → {ragas_path}")


def _print_final_instructions(n: int) -> None:
    print(f"\n{'='*80}")
    print("HOÀN TẤT! Làm tiếp theo:")
    print(f"  1. Xem kết quả terminal ở trên")
    print(f"  2. File results/latex_200_numbers.txt → copy vào LaTeX")
    print(f"  3. File results/eval_200_results.json → detail per answer")
    print(f"  4. File results/ragas_input_*.json → dùng cho LLM-as-judge")
    print(f"  5. Cập nhật các số n trong bảng (n={n})")
    print(f"{'='*80}")


def _filter_tc(tcs: list[dict], category: str | None = None) -> list[dict]:
    """Filter test cases by category. None = all."""
    if category is None:
        return tcs
    return [tc for tc in tcs if tc["category"] == category]


def main():
    parser = argparse.ArgumentParser(description="Evaluation with 200 questions")
    parser.add_argument("--method", choices=["zeroshot", "basic", "local", "global", "multihop"],
                        help="Chỉ chạy 1 phương pháp (test nhanh)")
    parser.add_argument("--no-latency", action="store_true", help="Bỏ qua đo latency")
    parser.add_argument("--economical", action="store_true",
                        help="Tiết kiệm: Global chỉ chạy TQ, Multihop chỉ chạy SL")
    args = parser.parse_args()

    # 1. Load 200 test cases
    test_cases = load_test_cases()
    n = len(test_cases)
    cats = sorted(set(tc["category"] for tc in test_cases))
    cat_counts = {c: sum(1 for tc in test_cases if tc["category"] == c) for c in cats}
    print(f"\nTổng test cases: {n}")
    print(f"  Phân bố: {', '.join(f'{c}={v}' for c, v in sorted(cat_counts.items()))}")
    for tc in test_cases:
        print(f"  [{tc['id']}] {tc['category']}/{tc['difficulty']}: {tc['question'][:70]}...")

    # 2. Load GraphRAG
    print(f"\nNạp GraphRAG artifacts từ: {ROOT_DIR}")
    from query.loader import GraphLoader
    loader = GraphLoader(ROOT_DIR).load()
    print("  → OK")

    # 3. Chọn câu hỏi đại diện cho latency
    LATENCY_QS = [
        ("Mức lương tối thiểu tháng vùng I theo quy định hiện hành trong corpus là bao nhiêu?", "lao_dong"),
        ("Người lao động có bao nhiêu ngày nghỉ phép năm tối thiểu?", "lao_dong"),
        ("Thời gian thử việc tối đa đối với công việc đòi hỏi trình độ chuyên môn từ cao đẳng trở lên là bao lâu?", "lao_dong"),
        ("Nghị định quy định lương tối thiểu vùng đang có hiệu lực là nghị định nào?", "lao_dong"),
        ("Người lao động đơn phương chấm dứt hợp đồng lao động đúng pháp luật có được hưởng trợ cấp thôi việc không?", "lao_dong"),
    ]

    # 4. Build methods (lazy to avoid expensive init for unused methods)
    _all_builders = [
        ("Zero-shot LLM",  _make_zeroshot),
        ("Basic Search",   lambda: _make_basic(loader)),
        ("Local Search",   lambda: _make_local(loader)),
        ("Global Search",  lambda: _make_global(loader)),
        ("Local+Multihop", lambda: _make_multihop(loader)),
    ]
    if args.method:
        mapping = {"zeroshot": 0, "basic": 1, "local": 2, "global": 3, "multihop": 4}
        name, builder = _all_builders[mapping[args.method]]
        methods = [(name, builder())]
    else:
        methods = [(n, b()) for n, b in _all_builders]

    # Economical filter: global→TQ, multihop→SL, others→all
    _ecofilter: dict[str, str | None] = {
        "Zero-shot LLM": None,
        "Basic Search": None,
        "Local Search": None,
        "Global Search": "comparative",
        "Local+Multihop": "multi_hop",
    }

    all_results: list[dict] = []
    try:
        for method_name, answer_fn in methods:
            if _should_stop():
                print(f"\n⚠️  Bỏ qua {method_name} do interrupt.")
                break

            tcs = _filter_tc(test_cases, _ecofilter.get(method_name) if args.economical else None)
            if not tcs:
                print(f"\n⚠️  Bỏ qua {method_name}: không có test case phù hợp.")
                continue

            r = evaluate_method(
                method_name, answer_fn, tcs,
                latency_qs=LATENCY_QS if not args.no_latency else None,
                n_latency=3,
            )
            all_results.append(r)

            # Lưu kết quả sau mỗi method (phòng khi interrupt/lỗi)
            _save_partial(all_results, test_cases)

            if _should_stop():
                print(f"\n⚠️  Dừng sau {method_name} do interrupt.")
                break

    except KeyboardInterrupt:
        print(f"\n⚠️  Người dùng ngắt (Ctrl+C).")
    except Exception as e:
        print(f"\n⚠️  Lỗi: {e}")

    # 5. Output (luôn lưu dù có partial result hay không)
    if all_results:
        _save_partial(all_results, test_cases)
        print_tables(all_results, test_cases)
    else:
        print("Không có kết quả nào để lưu.")

    _print_final_instructions(n)


if __name__ == "__main__":
    main()

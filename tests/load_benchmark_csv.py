"""Load QA benchmark CSV into dicts compatible with evaluation_suite."""

from __future__ import annotations

import csv
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent / "data" / "qa_benchmark_questions.csv"


def _split_field(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def load_benchmark_csv(
    path: Path | str | None = None,
    *,
    loai_cau_hoi: str | None = None,
    count_main_metrics_only: bool = False,
) -> list[dict]:
    """Load benchmark rows from CSV.

    Parameters
    ----------
    path:
        CSV path. Defaults to tests/data/qa_benchmark_questions.csv.
    loai_cau_hoi:
        Optional filter: TK, TQ, TH, SL, HL, NP.
    count_main_metrics_only:
        If True, exclude NP (negative) cases.
    """
    csv_path = Path(path) if path is not None else DEFAULT_CSV
    rows: list[dict] = []

    with csv_path.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            if loai_cau_hoi and raw["loai_cau_hoi"] != loai_cau_hoi:
                continue
            if count_main_metrics_only and raw.get("count_main_metrics") != "yes":
                continue

            rows.append({
                "id": raw["id"],
                "loai_cau_hoi": raw["loai_cau_hoi"],
                "domain": raw["domain"],
                "category": raw["nhan_ky_thuat"],
                "difficulty": raw["difficulty"],
                "search_mode_khuyen_nghi": raw["search_mode_khuyen_nghi"],
                "question": raw["question"],
                "expected_keywords": _split_field(raw["expected_keywords"]),
                "expected_citations": _split_field(raw["expected_citations"]),
                "reasoning_chain": raw.get("reasoning_chain") or None,
                "reference_answer": raw.get("reference_answer") or "",
                "in_corpus": raw.get("in_corpus") == "yes",
                "count_main_metrics": raw.get("count_main_metrics") == "yes",
                "source_van_ban": raw.get("source_van_ban") or "",
                "notes": raw.get("notes") or "",
            })

    return rows


def to_evaluation_suite_cases(rows: list[dict]) -> list[dict]:
    """Convert loaded rows to the shape expected by tests.evaluation_suite."""
    return [
        {
            "id": r["id"],
            "domain": r["domain"],
            "category": r["category"],
            "difficulty": r["difficulty"],
            "question": r["question"],
            "expected_keywords": r["expected_keywords"],
            "expected_citations": r["expected_citations"],
            **({"reasoning_chain": r["reasoning_chain"]} if r.get("reasoning_chain") else {}),
        }
        for r in rows
    ]

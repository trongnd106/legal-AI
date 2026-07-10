#!/usr/bin/env python3
"""
scripts/contract_benchmark.py
=============================
Benchmark rule-based contract analysis (VR001-VR016) with ground-truth test cases.

Computes per-rule TP / FP / FN / Precision / Recall / F1.
Outputs terminal table + LaTeX-ready snippet.

Cách chạy:
    python scripts/contract_benchmark.py

Yêu cầu:
    pip install pydantic
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# ── Add unified-search-app to path ────────────────────────────────────────
_APP = Path(__file__).resolve().parents[1] / "unified-search-app" / "app"

# Manually register contract_analysis modules to bypass __init__.py
import importlib.machinery
import types as _types

_constants_path = _APP / "contract_analysis" / "constants.py"
_schema_path    = _APP / "contract_analysis" / "schema.py"
_rules_path     = _APP / "contract_analysis" / "rules.py"

# Create contract_analysis package namespace
_ca_pkg = _types.ModuleType("contract_analysis")
_ca_pkg.__path__ = [str(_APP / "contract_analysis")]
_ca_pkg.__package__ = "contract_analysis"
_ca_pkg.__file__ = str(_APP / "contract_analysis" / "__init__.py")

import sys
sys.modules["contract_analysis"] = _ca_pkg

def _load_submodule(name: str, path: Path) -> _types.ModuleType:
    full_name = f"contract_analysis.{name}"
    mod = importlib.machinery.SourceFileLoader(full_name, str(path)).load_module()
    # Top-level __name__ won't match contract_analysis.xxx; fix it:
    if mod.__name__ != full_name:
        mod.__name__ = full_name
    mod.__package__ = "contract_analysis"
    mod.__path__ = []
    sys.modules[full_name] = mod
    setattr(_ca_pkg, name, mod)
    return mod

_constants_mod = _load_submodule("constants", _constants_path)
_schema_mod    = _load_submodule("schema", _schema_path)
_rules_mod     = _load_submodule("rules", _rules_path)

RuleContext  = _rules_mod.RuleContext
apply_rules  = _rules_mod.apply_rules
Clause       = _schema_mod.Clause


# ──────────────────────────────────────────────────────────────────────────────
# Test case definition
# ──────────────────────────────────────────────────────────────────────────────

def _c(
    clause_id: str,
    text: str,
    category: str = "UNKNOWN",
    categories: list[str] | None = None,
    summary: str = "",
) -> Clause:
    return Clause(
        clause_id=clause_id,
        category=category,
        categories=categories or [],
        original_text=text,
        summary=summary,
    )

# region = IV (min wage 3,450,000) by default
CTX = RuleContext(region="IV", max_probation_days=60)

TEST_CASES: list[Clause] = [
    # ── VR001: Lương < tối thiểu vùng ──────────────────────────────────────
    # Positive
    _c("vr001_p1", "Mức lương: 2.000.000 đồng/tháng.", "SALARY"),
    _c("vr001_p2", "Lương chính 3.000.000 VNĐ/tháng.", "SALARY"),
    _c("vr001_p3", "Tiền lương 1.500.000 đ/tháng.", "SALARY", ["SALARY", "WORKING_HOURS"]),
    # Negative (above threshold or no salary info)
    _c("vr001_n1", "Mức lương: 4.000.000 đồng/tháng.", "SALARY"),
    _c("vr001_n2", "Mức lương: 3.450.000 đồng/tháng.", "SALARY"),  # exactly at threshold
    _c("vr001_n3", "Mức lương: 10.000.000 đồng/tháng.", "SALARY"),
    _c("vr001_n4", "Thời giờ làm việc 40 giờ/tuần.", "WORKING_HOURS"),  # not salary

    # ── VR002: Thử việc > 60 ngày ──────────────────────────────────────────
    _c("vr002_p1", "Thời gian thử việc 90 ngày.", "PROBATION"),
    _c("vr002_p2", "Thử việc: 3 tháng.", "PROBATION"),
    # Negative
    _c("vr002_n1", "Thời gian thử việc 30 ngày.", "PROBATION"),
    _c("vr002_n2", "Thời gian thử việc 60 ngày.", "PROBATION"),  # exactly at threshold
    _c("vr002_n3", "Thời gian thử việc 45 ngày.", "PROBATION"),

    # ── VR003: Giờ làm/tuần > 48 & VR003B: Giờ/ngày > 8 ────────────────────
    _c("vr003_p1", "Thời giờ làm việc 52 giờ/tuần.", "WORKING_HOURS"),
    _c("vr003_p2", "Làm việc 10 giờ/ngày.", "WORKING_HOURS"),           # VR003B only
    _c("vr003_p3", "Thời giờ làm việc 55 giờ/tuần, 11 giờ/ngày.", "WORKING_HOURS"),  # VR003 + VR003B
    # Negative
    _c("vr003_n1", "Thời giờ làm việc 40 giờ/tuần.", "WORKING_HOURS"),
    _c("vr003_n2", "Thời giờ làm việc 48 giờ/tuần.", "WORKING_HOURS"),   # exactly at threshold
    _c("vr003_n3", "Làm việc 8 giờ/ngày.", "WORKING_HOURS"),            # exactly at threshold
    _c("vr003_n4", "Thời giờ làm việc 44 giờ/tuần, 7 giờ/ngày.", "WORKING_HOURS"),

    # ── VR004: Lương thử việc < 85% ────────────────────────────────────────
    _c("vr004_p1", "Lương thử việc 3.000.000, lương chính thức 10.000.000.", "PROBATION",
      ["PROBATION", "SALARY"]),
    # Negative
    _c("vr004_n1", "Lương thử việc 9.000.000, lương chính thức 10.000.000.", "PROBATION",
      ["PROBATION", "SALARY"]),    # 90% > 85%
    _c("vr004_n2", "Lương thử việc 8.500.000, lương chính thức 10.000.000.", "PROBATION",
      ["PROBATION", "SALARY"]),    # exactly 85%

    # ── VR005: Phạt tiền NLĐ ───────────────────────────────────────────────
    _c("vr005_p1", "NLĐ vi phạm nội quy sẽ bị phạt tiền 500.000 đồng.", "PENALTY_CLAUSE"),
    _c("vr005_p2", "Người lao động nếu vi phạm hợp đồng sẽ bị phạt tiền.", "UNKNOWN"),
    # Negative
    _c("vr005_n1", "NSDLĐ chậm trả lương sẽ bị phạt tiền theo luật.", "SALARY"),
    _c("vr005_n2", "Các bên tuân thủ quy định pháp luật.", "UNKNOWN"),

    # ── VR006: HĐLĐ xác định thời hạn > 36 tháng ───────────────────────────
    _c("vr006_p1", "Thời hạn hợp đồng: 48 tháng.", "CONTRACT_TYPE"),
    _c("vr006_p2", "Thời hạn 5 năm kể từ ngày ký.", "CONTRACT_DURATION"),
    # Negative
    _c("vr006_n1", "Thời hạn hợp đồng: 24 tháng.", "CONTRACT_TYPE"),
    _c("vr006_n2", "Hợp đồng không xác định thời hạn.", "CONTRACT_TYPE"),

    # ── VR007: Ký lần thứ ≥ 3 ─────────────────────────────────────────────
    _c("vr007_p1", "Ký lần thứ 3. Loại hợp đồng xác định thời hạn.", "CONTRACT_TYPE"),
    _c("vr007_p2", "Ký lần thứ 4, thời hạn 12 tháng.", "CONTRACT_TYPE"),
    # Negative
    _c("vr007_n1", "Ký lần thứ 2, thời hạn 12 tháng.", "CONTRACT_TYPE"),
    _c("vr007_n2", "Ký lần thứ 1. Hợp đồng không xác định thời hạn.", "CONTRACT_TYPE"),

    # ── VR008: Nghỉ phép < 12 ngày/năm ─────────────────────────────────────
    _c("vr008_p1", "Số ngày nghỉ phép năm: 10 ngày.", "LEAVE"),
    _c("vr008_p2", "Phép năm 8 ngày/năm.", "LEAVE"),
    # Negative
    _c("vr008_n1", "Số ngày nghỉ phép năm: 14 ngày.", "LEAVE"),
    _c("vr008_n2", "Ngày nghỉ phép năm: 12 ngày.", "LEAVE"),  # exactly at threshold
    _c("vr008_n3", "Không có điều khoản nghỉ phép.", "WORKING_HOURS"),

    # ── VR009: BHXH/BHYT không đề cập ──────────────────────────────────────
    _c("vr009_p1", "Chế độ bảo hiểm theo quy định của pháp luật.", "SOCIAL_INSURANCE"),
    # Negative (has both)
    _c("vr009_n1", "BHXH: 8%, BHYT: 1.5% theo quy định.", "SOCIAL_INSURANCE"),
    _c("vr009_n2", "Bảo hiểm xã hội và bảo hiểm y tế theo luật định.", "SOCIAL_INSURANCE"),
    # Only BHXH, no BHYT
    _c("vr009_partial", "BHXH đầy đủ theo quy định.", "SOCIAL_INSURANCE"),

    # ── VR010: Báo trước chấm dứt < 45 ngày (HĐLĐ vô thời hạn) ────────────
    _c("vr010_p1",
       "NLĐ đơn phương chấm dứt HĐLĐ không xác định thời hạn, báo trước 30 ngày.",
       "TERMINATION"),
    _c("vr010_p2",
       "Người lao động báo trước 20 ngày khi đơn phương chấm dứt HĐ không thời hạn.",
       "TERMINATION"),
    # Negative
    _c("vr010_n1",
       "NLĐ báo trước 60 ngày khi chấm dứt HĐLĐ không xác định thời hạn.",
       "TERMINATION"),
    _c("vr010_n2",
       "Hai bên thỏa thuận chấm dứt hợp đồng.",
       "TERMINATION"),  # not unilateral

    # ── VR011: Không đề cập trợ cấp thôi việc ─────────────────────────────
    _c("vr011_p1", "Chấm dứt HĐLĐ theo quy định pháp luật.", "TERMINATION"),
    # Negative
    _c("vr011_n1", "Khi chấm dứt HĐLĐ, NSDLĐ có trách nhiệm trả trợ cấp thôi việc.", "TERMINATION"),
    _c("vr011_n2", "Trợ cấp thôi việc và trợ cấp mất việc theo BLLĐ 2019.", "TERMINATION"),

    # ── VR012: Điều khoản bất lợi một chiều ───────────────────────────────
    _c("vr012_p1", "NSDLĐ có quyền điều chỉnh lương bất cứ lúc nào.", "UNILATERAL_TERMS"),
    _c("vr012_p2", "Công ty có quyền thay đổi công việc mà không cần NLĐ đồng ý.", "UNILATERAL_TERMS"),
    # Negative
    _c("vr012_n1", "Các bên thỏa thuận khi thay đổi điều khoản hợp đồng.", "UNKNOWN"),

    # ── VR013: Từ bỏ quyền lợi ────────────────────────────────────────────
    _c("vr013_p1", "NLĐ đồng ý từ bỏ quyền khiếu nại.", "WAIVER_CLAUSE"),
    _c("vr013_p2", "NLĐ miễn truy cứu trách nhiệm NSDLĐ.", "UNKNOWN"),
    # Negative
    _c("vr013_n1", "Các bên cam kết thực hiện đúng quy định pháp luật.", "UNKNOWN"),

    # ── VR014: Non-compete > 12 tháng ──────────────────────────────────────
    _c("vr014_p1", "NLĐ không được cạnh tranh trong vòng 24 tháng sau khi nghỉ việc.", "NON_COMPETE"),
    _c("vr014_p2", "Thời hạn không làm việc cho đối thủ: 3 năm.", "NON_COMPETE"),
    # Negative
    _c("vr014_n1", "NLĐ không được cạnh tranh trong vòng 6 tháng.", "NON_COMPETE"),
    _c("vr014_n2", "Thỏa thuận không cạnh tranh trong 12 tháng.", "NON_COMPETE"),  # exactly at threshold

    # ── VR015: Không có địa điểm làm việc ──────────────────────────────────
    _c("vr015_p1", "Bên A: Công ty XYZ. Bên B: NLĐ.", "PARTY_INFO"),
    _c("vr015_p2", "Thông tin các bên: NSDLĐ và NLĐ.", "PARTY_INFO"),
    # Negative (has workplace)
    _c("vr015_n1", "Bên A: Công ty ABC. Địa điểm làm việc: Hà Nội.", "PARTY_INFO",
      ["PARTY_INFO", "WORKPLACE"]),

    # ── VR016: Chu kỳ trả lương > 1 tháng ──────────────────────────────────
    _c("vr016_p1", "Trả lương 3 tháng/lần.", "SALARY"),
    _c("vr016_p2", "Lương được trả 6 tháng một lần.", "SALARY"),
    # Negative
    _c("vr016_n1", "Trả lương 1 tháng/lần.", "SALARY"),
    _c("vr016_n2", "Lương trả hàng tháng.", "SALARY"),
]

# ── Ground truth mapping ──────────────────────────────────────────────────────
# Explicit: for each test case, which rules should trigger?

GROUND_TRUTH: dict[str, set[str]] = {
    # VR001
    "vr001_p1":     {"VR001"},
    "vr001_p2":     {"VR001"},
    "vr001_p3":     {"VR001"},
    "vr001_n1":     set(),
    "vr001_n2":     set(),
    "vr001_n3":     set(),
    "vr001_n4":     set(),
    # VR002
    "vr002_p1":     {"VR002"},
    "vr002_p2":     {"VR002"},
    "vr002_n1":     set(),
    "vr002_n2":     set(),
    "vr002_n3":     set(),
    # VR003
    "vr003_p1":     {"VR003"},
    "vr003_p2":     {"VR003B"},
    "vr003_p3":     {"VR003", "VR003B"},
    "vr003_n1":     set(),
    "vr003_n2":     set(),
    "vr003_n3":     set(),
    "vr003_n4":     set(),
    # VR004
    "vr004_p1":     {"VR004"},
    "vr004_n1":     set(),
    "vr004_n2":     set(),
    # VR005
    "vr005_p1":     {"VR005"},
    "vr005_p2":     {"VR005"},
    "vr005_n1":     set(),
    "vr005_n2":     set(),
    # VR006
    "vr006_p1":     {"VR006"},
    "vr006_p2":     {"VR006"},
    "vr006_n1":     set(),
    "vr006_n2":     set(),
    # VR007
    "vr007_p1":     {"VR007"},
    "vr007_p2":     {"VR007"},
    "vr007_n1":     set(),
    "vr007_n2":     set(),
    # VR008
    "vr008_p1":     {"VR008"},
    "vr008_p2":     {"VR008"},
    "vr008_n1":     set(),
    "vr008_n2":     set(),
    "vr008_n3":     set(),
    # VR009
    "vr009_p1":     {"VR009", "VR009B"},
    "vr009_n1":     set(),
    "vr009_n2":     set(),
    "vr009_partial": {"VR009B"},    # has BHXH but no BHYT → only VR009B
    # VR010
    "vr010_p1":     {"VR010"},
    "vr010_p2":     {"VR010"},
    "vr010_n1":     set(),
    "vr010_n2":     set(),
    # VR011
    "vr011_p1":     {"VR011"},
    "vr011_n1":     set(),
    "vr011_n2":     set(),
    # VR012
    "vr012_p1":     {"VR012"},
    "vr012_p2":     {"VR012"},
    "vr012_n1":     set(),
    # VR013
    "vr013_p1":     {"VR013"},
    "vr013_p2":     {"VR013"},
    "vr013_n1":     set(),
    # VR014
    "vr014_p1":     {"VR014"},
    "vr014_p2":     {"VR014"},
    "vr014_n1":     set(),
    "vr014_n2":     set(),
    # VR015
    "vr015_p1":     {"VR015"},
    "vr015_p2":     {"VR015"},
    "vr015_n1":     set(),
    # VR016
    "vr016_p1":     {"VR016"},
    "vr016_p2":     {"VR016"},
    "vr016_n1":     set(),
    "vr016_n2":     set(),
}

# ── All rule IDs for reporting ────────────────────────────────────────────────
ALL_RULES = [
    "VR001", "VR002", "VR003", "VR003B", "VR004", "VR005", "VR006", "VR007",
    "VR008", "VR009", "VR009B", "VR010", "VR011", "VR012", "VR013", "VR014",
    "VR015", "VR016",
]

RULE_DESCRIPTIONS: dict[str, str] = {
    "VR001":  "Lương < mức tối thiểu vùng",
    "VR002":  "Thử việc > 60 ngày",
    "VR003":  "Giờ làm/tuần > 48",
    "VR003B": "Giờ làm/ngày > 8",
    "VR004":  "Lương thử việc < 85%",
    "VR005":  "Phạt tiền NLĐ",
    "VR006":  "HĐLĐ XĐTH > 36 tháng",
    "VR007":  "Ký HĐ XĐTH lần >= 3",
    "VR008":  "Nghỉ phép < 12 ngày/năm",
    "VR009":  "Thiếu BHXH",
    "VR009B": "Thiếu BHYT",
    "VR010":  "Báo trước chấm dứt < 45 ngày",
    "VR011":  "Thiếu trợ cấp thôi việc",
    "VR012":  "Điều khoản bất lợi một chiều",
    "VR013":  "Từ bỏ quyền lợi",
    "VR014":  "Non-compete > 12 tháng",
    "VR015":  "Thiếu địa điểm làm việc",
    "VR016":  "Chu kỳ trả lương > 1 tháng",
}


# ──────────────────────────────────────────────────────────────────────────────
# Benchmark execution
# ──────────────────────────────────────────────────────────────────────────────

def run_benchmark() -> dict[str, dict[str, int]]:
    """Run all test cases, return {rule: {tp, fp, fn}}."""
    counts: dict[str, dict[str, int]] = {
        r: {"tp": 0, "fp": 0, "fn": 0} for r in ALL_RULES
    }

    for clause in TEST_CASES:
        cid = clause.clause_id
        expected = GROUND_TRUTH.get(cid, set())
        predicted = {i.issue_id for i in apply_rules(clause, CTX)}

        for rule in ALL_RULES:
            exp = rule in expected
            pre = rule in predicted
            if pre and exp:
                counts[rule]["tp"] += 1
            elif pre and not exp:
                counts[rule]["fp"] += 1
            elif not pre and exp:
                counts[rule]["fn"] += 1
            # tn is not tracked (not meaningful for rule-level evaluation)

    return counts


# ──────────────────────────────────────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────────────────────────────────────

def print_terminal_table(counts: dict[str, dict[str, int]]) -> None:
    """Print a human-readable table."""
    header = f"{'Rule':<8} {'Description':<30} {'TP':>4} {'FP':>4} {'FN':>4} {'Prec':>7} {'Recall':>7} {'F1':>7}"
    sep = "-" * len(header)
    print("\n" + sep)
    print("BENCHMARK KẾT QUẢ PHÂN TÍCH HĐLĐ (VR001-VR016)")
    print(sep)
    print(header)
    print(sep)

    totals = {"tp": 0, "fp": 0, "fn": 0}
    for rule in ALL_RULES:
        c = counts[rule]
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn
        desc = RULE_DESCRIPTIONS.get(rule, "")
        print(f"{rule:<8} {desc:<30} {tp:>4} {fp:>4} {fn:>4} {prec:>6.1%} {rec:>6.1%} {f1:>6.1%}")

    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    prec_agg = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec_agg  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_agg   = 2 * prec_agg * rec_agg / (prec_agg + rec_agg) if (prec_agg + rec_agg) > 0 else 0.0
    print(sep)
    print(f"{'Tổng':<8} {'(micro avg)':<30} {tp:>4} {fp:>4} {fn:>4} {prec_agg:>6.1%} {rec_agg:>6.1%} {f1_agg:>6.1%}")
    print(sep)

    macro_prec = 0.0
    macro_rec = 0.0
    macro_f1 = 0.0
    n_active = 0
    for rule in ALL_RULES:
        c = counts[rule]
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        if tp + fp + fn > 0:
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            macro_prec += prec
            macro_rec += rec
            macro_f1 += f1
            n_active += 1
    if n_active > 0:
        macro_prec /= n_active
        macro_rec /= n_active
        macro_f1 /= n_active
    print(f"{'Macro avg':<8} {'':<30} {'':>4} {'':>4} {'':>4} {macro_prec:>6.1%} {macro_rec:>6.1%} {macro_f1:>6.1%}")
    print()


def print_latex_table(counts: dict[str, dict[str, int]]) -> None:
    """Print LaTeX-ready table rows (for Bảng 4.10)."""
    print("\n% --- LaTeX snippet: Bảng 4.10 (copy vào 4_Ket_qua_thuc_nghiem.tex) ---\n")
    for rule in ALL_RULES:
        c = counts[rule]
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        desc = RULE_DESCRIPTIONS.get(rule, "")
        print(f"    {rule:<8} & {desc:<30} & {tp:>3} & {fp:>3} & {fn:>3} & {prec:.1%} & {rec:.1%} & {f1:.1%} \\\\")

    tp = sum(counts[r]["tp"] for r in ALL_RULES)
    fp = sum(counts[r]["fp"] for r in ALL_RULES)
    fn = sum(counts[r]["fn"] for r in ALL_RULES)
    prec_agg = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec_agg = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_agg = 2 * prec_agg * rec_agg / (prec_agg + rec_agg) if (prec_agg + rec_agg) > 0 else 0.0
    print(f"    \\hline")
    print(f"    \\textbf{{Tổng}} & \\textbf{{(micro avg)}} & {tp:>3} & {fp:>3} & {fn:>3} & \\textbf{{{prec_agg:.1%}}} & \\textbf{{{rec_agg:.1%}}} & \\textbf{{{f1_agg:.1%}}} \\\\")
    print()


def check_coverage() -> None:
    """Warn if any rule has zero positive test cases."""
    for rule in ALL_RULES:
        n_pos = sum(1 for cid, exp in GROUND_TRUTH.items() if rule in exp)
        if n_pos == 0:
            print(f"[WARN] {rule}: không có test case positive nào!")
    print(f"Tổng số test cases: {len(TEST_CASES)}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 72)
    print("  CONTRACT ANALYSIS BENCHMARK  —  VR001–VR016")
    print("=" * 72)

    check_coverage()
    counts = run_benchmark()
    print_terminal_table(counts)
    print_latex_table(counts)

    print(f"\nKết thúc benchmark. Tổng số {len(TEST_CASES)} test cases, {len(ALL_RULES)} rules.")

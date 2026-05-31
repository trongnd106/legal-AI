# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Điểm tuân thủ và báo cáo Markdown — nâng cấp với executive summary + breakdown."""

from __future__ import annotations

from collections import Counter

from contract_analysis.constants import (
    MANDATORY_CLAUSE_LEGAL_BASIS,
    MISSING_MANDATORY_PENALTY,
    VIOLATION_SCORE_PENALTY,
)
from contract_analysis.schema import ContractAnalysisResult, ContractIssue

_EMOJI = {
    "VIOLATION":   "🔴",
    "HIGH_RISK":   "🟠",
    "MEDIUM_RISK": "🟡",
    "COMPLIANT":   "🟢",
    "NOT_COVERED": "⚪",
}

_SEVERITY_ORDER = ["VIOLATION", "HIGH_RISK", "MEDIUM_RISK", "NOT_COVERED", "COMPLIANT"]


def calculate_compliance_score(result: ContractAnalysisResult) -> float:
    """100 điểm trừ theo mức độ vấn đề và điều khoản thiếu."""
    score = 100.0
    seen: set[str] = set()
    for ca in result.per_clause:
        for iss in ca.rule_issues + ca.llm_issues:
            key = f"{iss.issue_id}:{iss.description[:80]}"
            if key in seen:
                continue
            seen.add(key)
            score -= VIOLATION_SCORE_PENALTY.get(iss.severity, 0)
    score -= MISSING_MANDATORY_PENALTY * len(result.missing_mandatory)
    return max(0.0, min(100.0, score))


def _all_issues(result: ContractAnalysisResult) -> list[ContractIssue]:
    """Tất cả issues không trùng lặp."""
    seen: set[str] = set()
    out: list[ContractIssue] = []
    for ca in result.per_clause:
        for iss in ca.rule_issues + ca.llm_issues:
            key = f"{iss.issue_id}:{iss.description[:80]}"
            if key not in seen:
                seen.add(key)
                out.append(iss)
    return out


def _score_badge(score: float) -> str:
    if score >= 90:
        return "🟢 Tốt"
    if score >= 70:
        return "🟡 Trung bình"
    if score >= 50:
        return "🟠 Cần cải thiện"
    return "🔴 Rủi ro cao"


def _priority_actions(issues: list[ContractIssue]) -> list[str]:
    """Top 5 vấn đề ưu tiên cần xử lý ngay."""
    violations = [i for i in issues if i.severity == "VIOLATION"]
    high_risks  = [i for i in issues if i.severity == "HIGH_RISK"]
    priority = (violations + high_risks)[:5]
    actions: list[str] = []
    for i, iss in enumerate(priority, 1):
        actions.append(
            f"{i}. {_EMOJI[iss.severity]} **{iss.description[:120]}**  \n"
            f"   → {iss.recommendation}"
        )
    return actions


def build_markdown_report(result: ContractAnalysisResult) -> str:
    """Báo cáo tiếng Việt 5 phần: tóm tắt · thiếu · rủi ro · breakdown · ghi chú."""
    m    = result.contract.metadata
    all_issues  = _all_issues(result)
    by_sev: Counter = Counter(i.severity for i in all_issues)

    lines: list[str] = ["## Báo cáo phân tích hợp đồng lao động", ""]

    # ── Phần 0: Executive Summary ─────────────────────────────────────────
    badge = _score_badge(result.compliance_score)
    lines += [
        "### 0. Tóm tắt nhanh",
        "",
        f"| Chỉ số | Giá trị |",
        f"|--------|---------|",
        f"| Điểm tuân thủ (ước lượng) | **{result.compliance_score:.1f}/100** {badge} |",
        f"| Độ tin cậy HĐLĐ | {m.labor_keyword_score:.0%} |",
        f"| File | {m.filename} — {m.extraction_method} |",
        f"| Số điều khoản | {len(result.clauses)} |",
        f"| Vi phạm (🔴) | {by_sev.get('VIOLATION', 0)} |",
        f"| Rủi ro cao (🟠) | {by_sev.get('HIGH_RISK', 0)} |",
        f"| Rủi ro trung bình (🟡) | {by_sev.get('MEDIUM_RISK', 0)} |",
        f"| Điều khoản bắt buộc thiếu | {len(result.missing_mandatory)} |",
        "",
    ]

    if result.analysis_session_id:
        lines.append(f"> Phiên phân tích (Neo4j): `{result.analysis_session_id}`\n")

    if m.contract_type == "unknown":
        lines += [
            "> ⚠️ Văn bản có thể **không phải** hợp đồng lao động điển hình "
            "(ít từ khóa). Kết quả chỉ mang tính tham khảo.",
            "",
        ]

    # ── Phần 1: Hành động ưu tiên ────────────────────────────────────────
    priority = _priority_actions(all_issues)
    lines += ["### 1. Hành động ưu tiên", ""]
    if priority:
        lines.extend(priority)
    else:
        lines.append("✅ Không có vi phạm/rủi ro cao rõ ràng.")
    lines.append("")

    # ── Phần 2: Điều khoản bắt buộc còn thiếu ────────────────────────────
    lines += ["### 2. Điều khoản bắt buộc còn thiếu"]
    if result.missing_mandatory:
        for k in result.missing_mandatory:
            basis = MANDATORY_CLAUSE_LEGAL_BASIS.get(k, k)
            lines.append(f"- 🟡 **{k}** — {basis}")
    else:
        lines.append("- ✅ Không phát hiện khuyết category bắt buộc rõ ràng.")
    lines.append("")

    # ── Phần 3: Rủi ro & vi phạm theo điều khoản ─────────────────────────
    lines += ["### 3. Rủi ro và vi phạm tiềm ẩn"]
    any_issue = False
    for ca in result.per_clause:
        all_cl_issues = ca.rule_issues + ca.llm_issues
        if not all_cl_issues:
            continue
        any_issue = True
        title = ca.clause.title or ca.clause.category
        lines.append(f"\n#### {title} (`{ca.clause.clause_id}`)")
        for iss in sorted(all_cl_issues, key=lambda i: _SEVERITY_ORDER.index(i.severity)):
            e = _EMOJI.get(iss.severity, "⚪")
            source = "rule" if iss.issue_id.startswith("VR") else "llm"
            lines.append(
                f"- {e} **{iss.severity}** [{iss.issue_id}·{source}]: {iss.description}  \n"
                f"  *Căn cứ:* {iss.legal_basis or '—'}  \n"
                f"  *Khuyến nghị:* {iss.recommendation or '—'}  \n"
                f"  *Bên bị ảnh hưởng:* {iss.affected_party or '—'}"
            )
    if not any_issue:
        lines.append("- ⚪ Không có cảnh báo rule/LLM rõ ràng trong phạm vi kiểm tra.")
    lines.append("")

    # ── Phần 4: Breakdown theo mức độ ────────────────────────────────────
    lines += ["### 4. Phân tích theo mức độ"]
    for sev in _SEVERITY_ORDER:
        count = by_sev.get(sev, 0)
        if count == 0:
            continue
        e = _EMOJI.get(sev, "⚪")
        group_issues = [i for i in all_issues if i.severity == sev]
        lines.append(f"\n**{e} {sev} ({count} vấn đề)**")
        for iss in group_issues:
            lines.append(f"  - [{iss.issue_id}] {iss.description[:120]}")
    if not all_issues:
        lines.append("✅ Không có vấn đề nào.")
    lines.append("")

    # ── Phần 5: Breakdown theo category ──────────────────────────────────
    lines += ["### 5. Phân tích theo điều khoản"]
    cat_summary: dict[str, list[str]] = {}
    for ca in result.per_clause:
        cat = ca.clause.category
        issues_str = [
            f"{_EMOJI.get(i.severity,'⚪')} {i.description[:80]}"
            for i in ca.rule_issues + ca.llm_issues
        ]
        cat_summary.setdefault(cat, []).extend(issues_str)

    for cat, iss_list in sorted(cat_summary.items()):
        mark = "✅" if not iss_list else ("🔴" if any("🔴" in s for s in iss_list) else "🟠")
        lines.append(f"- {mark} **{cat}**" + (f": {len(iss_list)} vấn đề" if iss_list else ": OK"))
    lines.append("")

    # ── Phần 6: Ghi chú ──────────────────────────────────────────────────
    lines += [
        "### 6. Ghi chú",
        "- Kết quả **không thay thế** tư vấn luật sư.",
        "- Mapping pháp luật: GraphRAG **basic_search** (text_units)"
        " + Neo4j `RELATED_TO` (khi bật).",
        "- Rules: VR001–VR016 áp dụng với BLLĐ 2019 + NĐ 74/2024.",
        "",
    ]

    return "\n".join(lines)


def finalize_report(result: ContractAnalysisResult) -> ContractAnalysisResult:
    """Gán điểm và markdown."""
    result.compliance_score = calculate_compliance_score(result)
    result.markdown_report  = build_markdown_report(result)
    return result

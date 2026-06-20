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

_SEVERITY_VI: dict[str, str] = {
    "VIOLATION":   "Vi phạm pháp luật",
    "HIGH_RISK":   "Rủi ro cao",
    "MEDIUM_RISK": "Cần lưu ý",
    "COMPLIANT":   "Tuân thủ",
    "NOT_COVERED": "Chưa xác định",
}

_CATEGORY_VI: dict[str, str] = {
    "PARTY_INFO":         "Thông tin các bên",
    "CONTRACT_TYPE":      "Loại hợp đồng",
    "CONTRACT_DURATION":  "Thời hạn hợp đồng",
    "JOB_DESCRIPTION":    "Mô tả công việc",
    "WORKPLACE":          "Địa điểm làm việc",
    "WORKING_HOURS":      "Thời giờ làm việc và nghỉ ngơi",
    "SALARY":             "Tiền lương",
    "SOCIAL_INSURANCE":   "Bảo hiểm xã hội, y tế",
    "TRAINING":           "Đào tạo và bồi dưỡng",
    "PROBATION":          "Thử việc",
    "ALLOWANCES":         "Phụ cấp và trợ cấp",
    "BONUS":              "Thưởng",
    "LEAVE":              "Nghỉ phép",
    "TERMINATION":        "Chấm dứt hợp đồng",
    "CONFIDENTIALITY":    "Bảo mật thông tin",
    "NON_COMPETE":        "Không cạnh tranh",
    "INTELLECTUAL_PROP":  "Sở hữu trí tuệ",
    "DISPUTE_RESOLUTION": "Giải quyết tranh chấp",
    "PENALTY_CLAUSE":     "Điều khoản phạt vi phạm",
    "UNILATERAL_TERMS":   "Điều khoản đơn phương",
    "WAIVER_CLAUSE":      "Từ bỏ quyền lợi",
    "UNKNOWN":            "Điều khoản khác",
}


def _vi_category(key: str) -> str:
    return _CATEGORY_VI.get(key, key)


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

    # ── Phần 0: Tóm tắt ──────────────────────────────────────────────────
    lines += [
        "### Tóm tắt",
        "",
        "| Thông tin | Chi tiết |",
        "|-----------|---------|",
        f"| Tên file | {m.filename} |",
        f"| Số điều khoản phân tích | {len(result.clauses)} |",
        f"| Vi phạm pháp luật 🔴 | {by_sev.get('VIOLATION', 0)} vấn đề |",
        f"| Rủi ro cao 🟠 | {by_sev.get('HIGH_RISK', 0)} vấn đề |",
        f"| Cần lưu ý 🟡 | {by_sev.get('MEDIUM_RISK', 0)} vấn đề |",
        f"| Điều khoản bắt buộc còn thiếu | {len(result.missing_mandatory)} mục |",
        "",
    ]

    if m.contract_type == "unknown":
        lines += [
            "> ⚠️ **Lưu ý:** Văn bản tải lên có thể không phải hợp đồng lao động "
            "điển hình. Kết quả phân tích chỉ mang tính tham khảo.",
            "",
        ]

    # ── Phần 1: Hành động ưu tiên ────────────────────────────────────────
    priority = _priority_actions(all_issues)
    lines += ["### Những điểm cần xử lý ngay", ""]
    if priority:
        lines.extend(priority)
    else:
        lines.append("✅ Không phát hiện vi phạm hay rủi ro cao đáng lo ngại.")
    lines.append("")

    # ── Phần 2: Điều khoản bắt buộc còn thiếu ────────────────────────────
    lines += ["### Điều khoản bắt buộc còn thiếu"]
    if result.missing_mandatory:
        for k in result.missing_mandatory:
            basis = MANDATORY_CLAUSE_LEGAL_BASIS.get(k, k)
            vi_name = _vi_category(k)
            lines.append(f"- 🟡 **{vi_name}** — {basis}")
    else:
        lines.append("- ✅ Hợp đồng đã có đầy đủ các điều khoản bắt buộc theo quy định.")
    lines.append("")

    # ── Phần 3: Rủi ro & vi phạm theo điều khoản ─────────────────────────
    lines += ["### Chi tiết rủi ro và vi phạm"]
    any_issue = False
    for ca in result.per_clause:
        all_cl_issues = ca.rule_issues + ca.llm_issues
        if not all_cl_issues:
            continue
        any_issue = True
        title = ca.clause.title or _vi_category(ca.clause.category)
        lines.append(f"\n#### {title}")
        for iss in sorted(all_cl_issues, key=lambda i: _SEVERITY_ORDER.index(i.severity)):
            e = _EMOJI.get(iss.severity, "⚪")
            sev_label = _SEVERITY_VI.get(iss.severity, iss.severity)
            lines.append(
                f"- {e} **{sev_label}:** {iss.description}  \n"
                f"  *Căn cứ pháp lý:* {iss.legal_basis or '—'}  \n"
                f"  *Khuyến nghị:* {iss.recommendation or '—'}  \n"
                f"  *Bên liên quan:* {iss.affected_party or '—'}"
            )
    if not any_issue:
        lines.append("✅ Không phát hiện vấn đề cụ thể trong phạm vi kiểm tra.")
    lines.append("")

    # ── Phần 4: Tổng hợp theo mức độ ──────────────────────────────────────
    lines += ["### Tổng hợp theo mức độ"]
    has_any = False
    for sev in _SEVERITY_ORDER:
        count = by_sev.get(sev, 0)
        if count == 0:
            continue
        has_any = True
        e = _EMOJI.get(sev, "⚪")
        sev_label = _SEVERITY_VI.get(sev, sev)
        group_issues = [i for i in all_issues if i.severity == sev]
        lines.append(f"\n**{e} {sev_label} ({count} vấn đề)**")
        for iss in group_issues:
            lines.append(f"  - {iss.description[:120]}")
    if not has_any:
        lines.append("✅ Không có vấn đề nào.")
    lines.append("")

    # ── Phần 5: Tổng hợp theo điều khoản ─────────────────────────────────
    lines += ["### Tổng hợp theo từng điều khoản"]
    cat_summary: dict[str, list[str]] = {}
    for ca in result.per_clause:
        cat = ca.clause.category
        issues_str = [
            f"{_EMOJI.get(i.severity,'⚪')} {i.description[:80]}"
            for i in ca.rule_issues + ca.llm_issues
        ]
        cat_summary.setdefault(cat, []).extend(issues_str)

    for cat, iss_list in sorted(cat_summary.items()):
        vi_name = _vi_category(cat)
        mark = "✅" if not iss_list else ("🔴" if any("🔴" in s for s in iss_list) else "🟠")
        lines.append(
            f"- {mark} **{vi_name}**"
            + (f": {len(iss_list)} vấn đề cần xem lại" if iss_list else ": Không có vấn đề")
        )
    lines.append("")

    # ── Phần 6: Lưu ý chung ──────────────────────────────────────────────
    lines += [
        "### Lưu ý",
        "- Kết quả phân tích này **không thay thế tư vấn từ luật sư** hoặc "
        "chuyên gia pháp lý. Nếu phát hiện vi phạm nghiêm trọng, bạn nên tham khảo "
        "ý kiến chuyên môn trước khi ký hợp đồng.",
        "- Phân tích dựa trên **Bộ luật Lao động 2019** và các nghị định hướng dẫn "
        "hiện hành (NĐ 74/2024).",
        "",
    ]

    return "\n".join(lines)


def finalize_report(result: ContractAnalysisResult) -> ContractAnalysisResult:
    """Gán điểm và markdown."""
    result.compliance_score = calculate_compliance_score(result)
    result.markdown_report  = build_markdown_report(result)
    return result

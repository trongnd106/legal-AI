# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Điểm tuân thủ và báo cáo Markdown."""

from __future__ import annotations

from contract_analysis.constants import (
    MANDATORY_CLAUSE_LEGAL_BASIS,
    MISSING_MANDATORY_PENALTY,
    VIOLATION_SCORE_PENALTY,
)
from contract_analysis.schema import ContractAnalysisResult


def calculate_compliance_score(result: ContractAnalysisResult) -> float:
    """100 điểm trừ theo mức độ vấn đề và điều khoản thiếu."""
    score = 100.0
    seen_issue_keys: set[str] = set()
    for ca in result.per_clause:
        for iss in ca.rule_issues + ca.llm_issues:
            key = f"{iss.issue_id}:{iss.description[:80]}"
            if key in seen_issue_keys:
                continue
            seen_issue_keys.add(key)
            penalty = VIOLATION_SCORE_PENALTY.get(iss.severity, 0)
            score -= penalty
    score -= MISSING_MANDATORY_PENALTY * len(result.missing_mandatory)
    return max(0.0, min(100.0, score))


def build_markdown_report(result: ContractAnalysisResult) -> str:
    """Báo cáo tiếng Việt có emoji mức độ."""
    m = result.contract.metadata
    lines: list[str] = [
        "## Báo cáo phân tích hợp đồng lao động",
        "",
        "### 1. Thông tin tổng quan",
        f"- **File:** {m.filename}",
        f"- **Trích xuất:** {m.extraction_method}",
    ]
    if result.analysis_session_id:
        lines.append(f"- **Phiên phân tích (Neo4j):** `{result.analysis_session_id}`")
    lines.extend([
        f"- **Điểm tuân thủ (ước lượng):** {result.compliance_score:.1f}/100",
        f"- **Độ tin cậy HĐLĐ (từ khóa):** {m.labor_keyword_score:.0%}",
        f"- **Số điều khoản:** {len(result.clauses)}",
        "",
    ])

    if m.contract_type == "unknown":
        lines += [
            "> ⚠️ Văn bản có thể **không phải** hợp đồng lao động điển hình "
            "(ít từ khóa). Kết quả chỉ mang tính tham khảo.",
            "",
        ]

    lines += ["### 2. Điều khoản bắt buộc còn thiếu"]
    if result.missing_mandatory:
        for k in result.missing_mandatory:
            basis = MANDATORY_CLAUSE_LEGAL_BASIS.get(k, k)
            lines.append(f"- 🟡 **{k}** — {basis}")
    else:
        lines.append("- ✅ Không phát hiện khuyết category bắt buộc rõ ràng (theo phân loại LLM).")
    lines.append("")

    lines += ["### 3. Rủi ro và vi phạm tiềm ẩn"]

    def emoji(sev: str) -> str:
        return {
            "VIOLATION": "🔴",
            "HIGH_RISK": "🟠",
            "MEDIUM_RISK": "🟡",
            "COMPLIANT": "🟢",
            "NOT_COVERED": "⚪",
        }.get(sev, "⚪")

    any_issue = False
    for ca in result.per_clause:
        block_title = f"#### {ca.clause.title or ca.clause.category} (`{ca.clause.clause_id}`)"
        sub: list[str] = []
        for iss in ca.rule_issues + ca.llm_issues:
            any_issue = True
            sub.append(
                f"- {emoji(iss.severity)} **{iss.severity}** [{iss.issue_id}]: {iss.description}\n"
                f"  - *Căn cứ:* {iss.legal_basis or '—'}\n"
                f"  - *Khuyến nghị:* {iss.recommendation or '—'}",
            )
        if sub:
            lines.append(block_title)
            lines.extend(sub)
            lines.append("")

    if not any_issue:
        lines.append("- ⚪ Không có cảnh báo rule/LLM rõ ràng trong phạm vi kiểm tra.")
        lines.append("")

    lines += [
        "### 4. Ghi chú",
        "- Kết quả **không thay thế** tư vấn luật sư.",
        "- Mapping pháp luật: **GraphRAG basic_search** (text_units) và — khi bật — **Neo4j** "
        "mở rộng `RELATED_TO` trên các **Entity** đã đồng bộ từ workspace.",
        "",
    ]

    return "\n".join(lines)


def finalize_report(result: ContractAnalysisResult) -> ContractAnalysisResult:
    """Gán điểm và markdown."""
    result.compliance_score = calculate_compliance_score(result)
    result.markdown_report = build_markdown_report(result)
    return result

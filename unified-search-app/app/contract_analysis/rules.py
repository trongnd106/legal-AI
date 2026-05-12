# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Rule-based phát hiện rủi ro nhanh (regex + ngưỡng)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contract_analysis.constants import REGIONAL_MINIMUM_WAGE
from contract_analysis.schema import Clause, ContractIssue


@dataclass
class RuleContext:
    region: str = "IV"
    # probation cap ngày — mặc định bảo thủ 60 (đại học); có thể chỉnh UI
    max_probation_days: int = 60


def extract_monthly_salary_vnd(text: str) -> int | None:
    """Tìm số tiền lương VNĐ trong đoạn văn (ưu tiên số lớn nhất hợp lý)."""
    # 5.000.000 hoặc 5000000
    patterns = [
        r"(?:lương|mức lương|tiền lương)[^\d]{0,40}(\d{1,3}(?:\.\d{3})+|\d{5,10})\s*(?:đồng|vnđ|đ)?",
        r"(\d{1,3}(?:\.\d{3})+)\s*(?:đồng|vnđ|đ)/tháng",
        r"(\d{5,10})\s*(?:đồng|vnđ|đ)/tháng",
    ]
    amounts: list[int] = []
    lower = text.lower()
    for pat in patterns:
        for m in re.finditer(pat, lower, re.IGNORECASE):
            raw = m.group(1).replace(".", "")
            try:
                val = int(raw)
            except ValueError:
                continue
            if 1_000_000 <= val <= 500_000_000:
                amounts.append(val)
    return max(amounts) if amounts else None


def extract_probation_days(text: str) -> int | None:
    """Ước lượng ngày thử việc từ '30 ngày', '2 tháng', ..."""
    t = text.lower()
    m = re.search(
        r"thử việc[^\d]{0,40}(\d+)\s*(?:ngày)",
        t,
    )
    if m:
        return int(m.group(1))
    m = re.search(r"thử việc[^\d]{0,40}(\d+)\s*(?:tháng)", t)
    if m:
        return int(m.group(1)) * 30
    return None


def extract_weekly_hours(text: str) -> float | None:
    t = text.lower()
    m = re.search(r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*/\s*tuần", t)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(
        r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*mỗi\s*tuần",
        t,
    )
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def apply_rules(clause: Clause, ctx: RuleContext) -> list[ContractIssue]:
    """Áp rule VR001–VR006 đơn giản (đại diện trong skill)."""
    issues: list[ContractIssue] = []
    cat = clause.category.upper()
    blob = f"{clause.original_text}\n{clause.summary}"

    if cat == "SALARY":
        salary = extract_monthly_salary_vnd(blob)
        cap = REGIONAL_MINIMUM_WAGE.get(ctx.region, REGIONAL_MINIMUM_WAGE["IV"])
        if salary is not None and salary < cap:
            issues.append(
                ContractIssue(
                    issue_id="VR001",
                    description=f"Mức lương ({salary:,} đ/tháng) có thể thấp hơn lương tối thiểu vùng {ctx.region} ({cap:,} đ/tháng).",
                    severity="VIOLATION",
                    legal_basis="Điều 91 BLLĐ 2019; Nghị định về lương tối thiểu vùng",
                    recommendation=f"Điều chỉnh mức lương ≥ {cap:,} đ/tháng hoặc xác minh vùng áp dụng.",
                    affected_party="NLĐ",
                    clause_id=clause.clause_id,
                )
            )

    if cat == "PROBATION":
        days = extract_probation_days(blob)
        if days is not None and days > ctx.max_probation_days:
            issues.append(
                ContractIssue(
                    issue_id="VR002",
                    description=f"Thời gian thử việc ({days} ngày) có thể vượt ngưỡng tham chiếu ({ctx.max_probation_days} ngày) cho nhóm công việc được giả định.",
                    severity="VIOLATION",
                    legal_basis="Điều 25 BLLĐ 2019",
                    recommendation="Rà soát chức danh và thời gian thử việc theo đúng nhóm (30/60/180 ngày).",
                    affected_party="NLĐ",
                    clause_id=clause.clause_id,
                )
            )

    if cat == "WORKING_HOURS":
        h = extract_weekly_hours(blob)
        if h is not None and h > 48:
            issues.append(
                ContractIssue(
                    issue_id="VR003",
                    description=f"Thời giờ làm việc ({h} giờ/tuần) vượt 48 giờ/tuần trong điều kiện làm việc thông thường.",
                    severity="VIOLATION",
                    legal_basis="Điều 105 BLLĐ 2019",
                    recommendation="Điều chỉnh hoặc bổ sung quy định làm thêm giờ/nghỉ bù hợp pháp.",
                    affected_party="NLĐ",
                    clause_id=clause.clause_id,
                )
            )

    if cat == "PROBATION":
        # VR004: lương thử việc < 85% — heuristic đơn giản nếu có hai mức số
        nums = re.findall(r"(\d{1,3}(?:\.\d{3})+|\d{5,10})", blob.lower())
        vals = []
        for n in nums:
            try:
                v = int(n.replace(".", ""))
            except ValueError:
                continue
            if 2_000_000 <= v <= 100_000_000:
                vals.append(v)
        vals = sorted(set(vals))
        if len(vals) >= 2:
            low, high = vals[0], vals[-1]
            if high > 0 and low / high < 0.85:
                issues.append(
                    ContractIssue(
                        issue_id="VR004",
                        description="Mức lương thử việc có thể dưới 85% so với mức cao hơn trong cùng điều khoản (heuristic).",
                        severity="HIGH_RISK",
                        legal_basis="Điều 26 BLLĐ 2019",
                        recommendation="Đảm bảo lương thử việc ≥ 85% mức lương theo hợp đồng.",
                        affected_party="NLĐ",
                        clause_id=clause.clause_id,
                    )
                )

    if cat == "PENALTY_CLAUSE":
        if re.search(r"phạt\s+tiền", blob.lower()) and re.search(
            r"người lao động|nlđ",
            blob.lower(),
        ):
            issues.append(
                ContractIssue(
                    issue_id="VR006",
                    description="Điều khoản có thể liên quan phạt tiền đối với NLĐ — cần đối chiếu kỷ luật lao động.",
                    severity="HIGH_RISK",
                    legal_basis="Điều 127 BLLĐ 2019 — hạn chế phạt tiền thay kỷ luật",
                    recommendation="Rà soát với chuyên gia; tránh phạt tiền trái quy định.",
                    affected_party="NLĐ",
                    clause_id=clause.clause_id,
                )
            )

    return issues

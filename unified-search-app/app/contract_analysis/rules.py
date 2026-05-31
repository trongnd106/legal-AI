# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Rule-based phát hiện rủi ro nhanh (regex + ngưỡng).

Rules VR001–VR016 áp dụng cho hợp đồng lao động Việt Nam.
Tất cả rules chạy đồng bộ (không LLM) — dưới 5ms/clause.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from contract_analysis.constants import REGIONAL_MINIMUM_WAGE
from contract_analysis.schema import Clause, ContractIssue


@dataclass
class RuleContext:
    region: str = "IV"
    # probation cap ngày — mặc định bảo thủ 60 (đại học)
    max_probation_days: int = 60


# ──────────────────────────────────────────────────────────────────────────────
# Helpers: trích xuất giá trị từ văn bản
# ──────────────────────────────────────────────────────────────────────────────

def extract_monthly_salary_vnd(text: str) -> int | None:
    """Tìm mức lương tháng (VNĐ). Ưu tiên số lớn nhất hợp lý."""
    patterns = [
        r"(?:lương|mức lương|tiền lương|lương chính)[^\d]{0,40}"
        r"(\d{1,3}(?:\.\d{3})+|\d{5,10})\s*(?:đồng|vnđ|đ)?",
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
    """Ước lượng số ngày thử việc từ '30 ngày', '2 tháng', ..."""
    t = text.lower()
    m = re.search(r"thử\s*việc[^\d]{0,50}(\d+)\s*(?:ngày)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"thử\s*việc[^\d]{0,50}(\d+)\s*(?:tháng)", t)
    if m:
        return int(m.group(1)) * 30
    return None


def extract_weekly_hours(text: str) -> float | None:
    """Tìm số giờ/tuần."""
    t = text.lower()
    for pat in [
        r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*/\s*tuần",
        r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*mỗi\s*tuần",
        r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*một\s*tuần",
    ]:
        m = re.search(pat, t)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def extract_daily_hours(text: str) -> float | None:
    """Tìm số giờ/ngày."""
    t = text.lower()
    for pat in [
        r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*/\s*ngày",
        r"(\d{1,2}(?:[\.,]\d+)?)\s*giờ\s*mỗi\s*ngày",
        r"làm\s+việc[^\d]{0,20}(\d{1,2}(?:[\.,]\d+)?)\s*giờ",
    ]:
        m = re.search(pat, t)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def extract_annual_leave_days(text: str) -> int | None:
    """Tìm số ngày nghỉ phép/năm."""
    t = text.lower()
    for pat in [
        r"(\d+)\s*ngày[^\d]{0,20}(?:nghỉ phép|phép năm|nghỉ hàng năm)",
        r"(?:nghỉ phép|phép năm)[^\d]{0,40}(\d+)\s*ngày",
        r"(\d+)\s*ngày\s*/\s*năm",
    ]:
        m = re.search(pat, t)
        if m:
            return int(m.group(1))
    return None


def extract_contract_months(text: str) -> int | None:
    """Tìm thời hạn hợp đồng (tháng)."""
    t = text.lower()
    m = re.search(r"thời\s+hạn[^\d]{0,40}(\d+)\s*tháng", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*tháng\s*kể\s*từ", t)
    if m:
        return int(m.group(1))
    m = re.search(r"thời\s+hạn[^\d]{0,40}(\d+)\s*năm", t)
    if m:
        return int(m.group(1)) * 12
    return None


def extract_notice_days(text: str) -> int | None:
    """Tìm thời gian báo trước khi chấm dứt HĐ."""
    t = text.lower()
    for pat in [
        r"báo\s+trước[^\d]{0,30}(\d+)\s*ngày",
        r"(\d+)\s*ngày[^\d]{0,20}báo\s+trước",
        r"thông\s+báo\s+trước[^\d]{0,30}(\d+)\s*ngày",
    ]:
        m = re.search(pat, t)
        if m:
            return int(m.group(1))
    return None


def _new_issue(issue_id: str, **kwargs) -> ContractIssue:
    return ContractIssue(issue_id=issue_id, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# apply_rules — toàn bộ 16 rules, chạy đồng bộ
# ──────────────────────────────────────────────────────────────────────────────

def apply_rules(clause: Clause, ctx: RuleContext) -> list[ContractIssue]:
    """Kiểm tra VR001–VR016.  < 5ms/clause."""
    issues: list[ContractIssue] = []
    cats = clause.effective_categories()           # set, uppercase
    blob = f"{clause.original_text}\n{clause.summary}".lower()
    cid  = clause.clause_id
    cap  = REGIONAL_MINIMUM_WAGE.get(ctx.region, REGIONAL_MINIMUM_WAGE["IV"])

    # ── VR001: Lương < tối thiểu vùng ──────────────────────────────────────
    if "SALARY" in cats:
        salary = extract_monthly_salary_vnd(blob)
        if salary is not None and salary < cap:
            issues.append(_new_issue(
                "VR001",
                description=(
                    f"Mức lương ({salary:,} đ/tháng) thấp hơn lương tối thiểu "
                    f"vùng {ctx.region} ({cap:,} đ/tháng)."
                ),
                severity="VIOLATION",
                legal_basis="Điều 91 BLLĐ 2019; NĐ 74/2024/NĐ-CP",
                recommendation=f"Điều chỉnh mức lương ≥ {cap:,} đ/tháng.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR002: Thử việc vượt hạn mức ──────────────────────────────────────
    if "PROBATION" in cats:
        days = extract_probation_days(blob)
        if days is not None and days > ctx.max_probation_days:
            issues.append(_new_issue(
                "VR002",
                description=(
                    f"Thời gian thử việc ({days} ngày) vượt ngưỡng tham chiếu "
                    f"({ctx.max_probation_days} ngày) cho chức danh được giả định."
                ),
                severity="VIOLATION",
                legal_basis="Điều 25 BLLĐ 2019 — 30/60/180 ngày tuỳ chức danh",
                recommendation="Rà soát chức danh và giới hạn thử việc theo nhóm.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR003: Giờ làm/tuần > 48 ───────────────────────────────────────────
    if "WORKING_HOURS" in cats:
        h_week = extract_weekly_hours(blob)
        if h_week is not None and h_week > 48:
            issues.append(_new_issue(
                "VR003",
                description=f"Thời giờ làm việc ({h_week} giờ/tuần) vượt 48 giờ/tuần.",
                severity="VIOLATION",
                legal_basis="Điều 105 BLLĐ 2019",
                recommendation="Điều chỉnh ≤ 48 giờ/tuần hoặc bổ sung quy định làm thêm giờ.",
                affected_party="NLĐ", clause_id=cid,
            ))

        h_day = extract_daily_hours(blob)
        if h_day is not None and h_day > 8:
            issues.append(_new_issue(
                "VR003B",
                description=f"Thời giờ làm việc ({h_day} giờ/ngày) vượt 8 giờ/ngày.",
                severity="HIGH_RISK",
                legal_basis="Điều 105 BLLĐ 2019 — giới hạn 8 giờ/ngày",
                recommendation="Điều chỉnh ≤ 8 giờ/ngày hoặc áp dụng quy định làm thêm giờ hợp pháp.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR004: Lương thử việc < 85% ────────────────────────────────────────
    if "PROBATION" in cats:
        nums = re.findall(r"(\d{1,3}(?:\.\d{3})+|\d{5,10})", blob)
        vals = sorted({int(n.replace(".", "")) for n in nums
                       if 2_000_000 <= _safe_int(n.replace(".", "")) <= 100_000_000})
        if len(vals) >= 2 and vals[-1] > 0 and vals[0] / vals[-1] < 0.85:
            issues.append(_new_issue(
                "VR004",
                description=(
                    f"Mức lương thấp nhất ({vals[0]:,}đ) < 85% mức cao nhất "
                    f"({vals[-1]:,}đ) trong điều khoản thử việc (heuristic)."
                ),
                severity="HIGH_RISK",
                legal_basis="Điều 26 BLLĐ 2019",
                recommendation="Đảm bảo lương thử việc ≥ 85% mức lương chính thức.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR005: Phạt tiền NLĐ (bị cấm) ─────────────────────────────────────
    if "PENALTY_CLAUSE" in cats or re.search(r"phạt\s+tiền", blob):
        if re.search(r"(?:người lao động|nlđ|bên b)[^\n]{0,80}phạt\s+tiền", blob):
            issues.append(_new_issue(
                "VR005",
                description="Điều khoản phạt tiền đối với NLĐ có thể vi phạm BLLĐ 2019.",
                severity="VIOLATION",
                legal_basis="Điều 127 BLLĐ 2019 — cấm phạt tiền thay kỷ luật lao động",
                recommendation="Thay thế bằng hình thức kỷ luật hợp pháp (khiển trách, sa thải...)",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR006: HĐLĐ xác định thời hạn > 36 tháng ──────────────────────────
    if "CONTRACT_DURATION" in cats or "CONTRACT_TYPE" in cats:
        months = extract_contract_months(blob)
        if months is not None and months > 36:
            is_indef = bool(re.search(r"không\s+xác\s+định\s+thời\s+hạn", blob))
            if not is_indef:
                issues.append(_new_issue(
                    "VR006",
                    description=(
                        f"Thời hạn hợp đồng ({months} tháng) vượt 36 tháng. "
                        "HĐLĐ xác định thời hạn tối đa 36 tháng (Điều 20)."
                    ),
                    severity="HIGH_RISK",
                    legal_basis="Điều 20 BLLĐ 2019 — tối đa 36 tháng cho HĐLĐ xác định thời hạn",
                    recommendation="Chuyển sang HĐLĐ không xác định thời hạn hoặc điều chỉnh.",
                    affected_party="cả hai", clause_id=cid,
                ))

    # ── VR007: Ký HĐLĐ xác định thời hạn lần ≥ 3 → phải vô thời hạn ───────
    if "CONTRACT_TYPE" in cats:
        lan_thu = re.search(r"ký\s+lần\s+thứ\s+(\d+)", blob)
        if lan_thu and int(lan_thu.group(1)) >= 3:
            if not re.search(r"không\s+xác\s+định\s+thời\s+hạn", blob):
                issues.append(_new_issue(
                    "VR007",
                    description=(
                        f"Hợp đồng ký lần thứ {lan_thu.group(1)} — nếu xác định "
                        "thời hạn sẽ vi phạm Điều 20 (hết 2 lần phải chuyển vô thời hạn)."
                    ),
                    severity="VIOLATION",
                    legal_basis="Điều 20 BLLĐ 2019 — chỉ được ký 1 lần xác định thời hạn tiếp",
                    recommendation="Chuyển sang HĐLĐ không xác định thời hạn.",
                    affected_party="cả hai", clause_id=cid,
                ))

    # ── VR008: Nghỉ phép < 12 ngày/năm ────────────────────────────────────
    if "LEAVE" in cats or "WORKING_HOURS" in cats:
        leave_days = extract_annual_leave_days(blob)
        if leave_days is not None and leave_days < 12:
            issues.append(_new_issue(
                "VR008",
                description=(
                    f"Ngày nghỉ phép năm ({leave_days} ngày) thấp hơn tối thiểu 12 ngày."
                ),
                severity="VIOLATION",
                legal_basis="Điều 113 BLLĐ 2019 — tối thiểu 12 ngày/năm",
                recommendation="Điều chỉnh ≥ 12 ngày phép/năm.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR009: BHXH/BHYT không đề cập ─────────────────────────────────────
    if "SOCIAL_INSURANCE" in cats:
        has_bhxh = bool(re.search(r"bhxh|bảo\s+hiểm\s+xã\s+hội", blob))
        has_bhyt = bool(re.search(r"bhyt|bảo\s+hiểm\s+y\s+tế", blob))
        if not has_bhxh:
            issues.append(_new_issue(
                "VR009",
                description="Điều khoản BHXH không đề cập rõ ràng nghĩa vụ đóng BHXH.",
                severity="HIGH_RISK",
                legal_basis="Điều 95 BLLĐ 2019; Luật BHXH 2014",
                recommendation="Bổ sung nghĩa vụ đóng BHXH bắt buộc (NLĐ 8%, NSDLĐ 17,5%).",
                affected_party="NLĐ", clause_id=cid,
            ))
        if not has_bhyt:
            issues.append(_new_issue(
                "VR009B",
                description="Không đề cập BHYT — bắt buộc theo Luật BHYT.",
                severity="MEDIUM_RISK",
                legal_basis="Điều 21.1h BLLĐ 2019; Luật BHYT",
                recommendation="Bổ sung quy định về BHYT.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR010: Điều khoản chấm dứt không có báo trước đủ ──────────────────
    if "TERMINATION" in cats:
        notice = extract_notice_days(blob)
        has_nld_terminate = bool(
            re.search(r"(?:người lao động|nlđ|bên b)[^\n]{0,120}đơn phương\s+chấm\s+dứt", blob)
        )
        if has_nld_terminate and notice is not None and notice < 45:
            # 45 ngày HĐLĐ không xác định thời hạn — Điều 35.2a
            if re.search(r"không\s+xác\s+định\s+thời\s+hạn", blob):
                issues.append(_new_issue(
                    "VR010",
                    description=(
                        f"Thời gian báo trước khi NLĐ chấm dứt HĐLĐ không xác định "
                        f"thời hạn ({notice} ngày) có thể thấp hơn 45 ngày."
                    ),
                    severity="HIGH_RISK",
                    legal_basis="Điều 35.2a BLLĐ 2019 — 45 ngày báo trước HĐLĐ vô thời hạn",
                    recommendation="Quy định ≥ 45 ngày báo trước cho HĐLĐ không xác định thời hạn.",
                    affected_party="cả hai", clause_id=cid,
                ))

    # ── VR011: Không có điều khoản trợ cấp thôi việc ──────────────────────
    if "TERMINATION" in cats:
        has_trocap = bool(re.search(
            r"trợ\s+cấp\s+thôi\s+việc|trợ\s+cấp\s+mất\s+việc",
            blob,
        ))
        if not has_trocap:
            issues.append(_new_issue(
                "VR011",
                description=(
                    "Điều khoản chấm dứt không đề cập trợ cấp thôi việc — "
                    "NLĐ có quyền nhận theo luật."
                ),
                severity="MEDIUM_RISK",
                legal_basis="Điều 46 BLLĐ 2019",
                recommendation="Bổ sung hoặc dẫn chiếu quy định trợ cấp thôi việc.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR012: Điều khoản bất lợi một chiều ────────────────────────────────
    if "UNILATERAL_TERMS" in cats:
        issues.append(_new_issue(
            "VR012",
            description=(
                "Phát hiện điều khoản có thể áp đặt quyền đơn phương bất lợi "
                "cho NLĐ — cần rà soát."
            ),
            severity="HIGH_RISK",
            legal_basis="Điều 9 BLLĐ 2019 — nguyên tắc thỏa thuận bình đẳng",
            recommendation="Rà soát với chuyên gia pháp lý.",
            affected_party="NLĐ", clause_id=cid,
        ))

    # ── VR013: Điều khoản từ bỏ quyền lợi (vô hiệu) ───────────────────────
    if "WAIVER_CLAUSE" in cats or re.search(
        r"từ\s+bỏ\s+(quyền|lợi\s+ích)|không\s+khiếu\s+nại|miễn\s+truy\s+cứu",
        blob,
    ):
        issues.append(_new_issue(
            "VR013",
            description=(
                "Điều khoản có thể yêu cầu NLĐ từ bỏ quyền lợi pháp luật bảo vệ "
                "— vô hiệu theo BLLĐ."
            ),
            severity="HIGH_RISK",
            legal_basis="Điều 9.2 BLLĐ 2019 — không được thỏa thuận thấp hơn tiêu chuẩn pháp luật",
            recommendation="Xóa hoặc sửa điều khoản từ bỏ quyền; tham khảo luật sư.",
            affected_party="NLĐ", clause_id=cid,
        ))

    # ── VR014: Non-compete > 12 tháng ──────────────────────────────────────
    if "NON_COMPETE" in cats:
        nc_months = _extract_non_compete_months(blob)
        if nc_months is not None and nc_months > 12:
            issues.append(_new_issue(
                "VR014",
                description=(
                    f"Điều khoản không cạnh tranh ({nc_months} tháng) thường bị tòa "
                    "xem là quá dài và khó được bảo vệ."
                ),
                severity="MEDIUM_RISK",
                legal_basis="Án lệ + Điều 9 BLLĐ 2019 — quyền làm việc",
                recommendation="Giới hạn ≤ 12 tháng; kèm bồi thường cụ thể.",
                affected_party="NLĐ", clause_id=cid,
            ))

    # ── VR015: Không đề cập địa điểm làm việc ─────────────────────────────
    if "PARTY_INFO" in cats and "WORKPLACE" not in {c.category.upper() for c in [clause]}:
        if not re.search(r"địa\s+điểm\s+làm\s+việc|nơi\s+làm\s+việc|trụ\s+sở", blob):
            issues.append(_new_issue(
                "VR015",
                description="Không tìm thấy điều khoản địa điểm làm việc rõ ràng.",
                severity="MEDIUM_RISK",
                legal_basis="Điều 21.1d BLLĐ 2019",
                recommendation="Bổ sung địa điểm làm việc cụ thể.",
                affected_party="cả hai", clause_id=cid,
            ))

    # ── VR016: Thời hạn trả lương > 1 tháng ────────────────────────────────
    if "SALARY" in cats:
        m = re.search(r"trả\s+lương[^\d]{0,50}(\d+)\s*(tháng|lần\s*/\s*tháng)", blob)
        if m and m.group(2).startswith("tháng"):
            interval_months = int(m.group(1))
            if interval_months > 1:
                issues.append(_new_issue(
                    "VR016",
                    description=(
                        f"Chu kỳ trả lương ({interval_months} tháng/lần) dài hơn 1 tháng — "
                        "có thể vi phạm quy định."
                    ),
                    severity="HIGH_RISK",
                    legal_basis="Điều 97 BLLĐ 2019 — trả lương ít nhất 1 lần/tháng",
                    recommendation="Điều chỉnh chu kỳ trả lương ≤ 1 tháng/lần.",
                    affected_party="NLĐ", clause_id=cid,
                ))

    return issues


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_int(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return 0


def _extract_non_compete_months(text: str) -> int | None:
    m = re.search(
        r"(?:không\s+cạnh\s+tranh|không\s+làm\s+việc\s+cho)[^\d]{0,60}(\d+)\s*tháng",
        text,
    )
    if m:
        return int(m.group(1))
    m = re.search(
        r"(?:không\s+cạnh\s+tranh|không\s+làm\s+việc\s+cho)[^\d]{0,60}(\d+)\s*năm",
        text,
    )
    if m:
        return int(m.group(1)) * 12
    return None

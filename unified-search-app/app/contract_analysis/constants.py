# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Hằng số: từ khóa HĐLĐ, điều khoản bắt buộc, ngưỡng lương tối thiểu."""

LABOR_CONTRACT_KEYWORDS = [
    "hợp đồng lao động",
    "người lao động",
    "người sử dụng lao động",
    "mức lương",
    "thời gian thử việc",
    "bảo hiểm xã hội",
    "thời giờ làm việc",
    "địa điểm làm việc",
]

MANDATORY_CLAUSE_KEYS = frozenset({
    "PARTY_INFO",
    "CONTRACT_TYPE",
    "CONTRACT_DURATION",
    "JOB_DESCRIPTION",
    "WORKPLACE",
    "WORKING_HOURS",
    "SALARY",
    "SOCIAL_INSURANCE",
    "TRAINING",
})

MANDATORY_CLAUSE_LEGAL_BASIS: dict[str, str] = {
    "PARTY_INFO": "Điều 21.1a BLLĐ 2019 — Tên, địa chỉ các bên",
    "CONTRACT_TYPE": "Điều 21.1b BLLĐ 2019 — Loại hợp đồng",
    "JOB_DESCRIPTION": "Điều 21.1c BLLĐ 2019 — Công việc phải làm",
    "WORKPLACE": "Điều 21.1d BLLĐ 2019 — Địa điểm làm việc",
    "CONTRACT_DURATION": "Điều 21.1đ BLLĐ 2019 — Thời hạn hợp đồng",
    "WORKING_HOURS": "Điều 21.1e BLLĐ 2019 — Thời giờ làm việc, nghỉ ngơi",
    "SALARY": "Điều 21.1g BLLĐ 2019 — Mức lương, hình thức trả lương",
    "SOCIAL_INSURANCE": "Điều 21.1h BLLĐ 2019 — Chế độ BHXH, BHYT",
    "TRAINING": "Điều 21.1i BLLĐ 2019 — Đào tạo, bồi dưỡng nâng cao kỹ năng",
}

CLAUSE_CATEGORIES_FOR_PROMPT = """
PARTY_INFO, CONTRACT_TYPE, CONTRACT_DURATION, JOB_DESCRIPTION, WORKPLACE,
WORKING_HOURS, SALARY, SOCIAL_INSURANCE, TRAINING,
PROBATION, ALLOWANCES, BONUS, LEAVE, TERMINATION, CONFIDENTIALITY,
NON_COMPETE, INTELLECTUAL_PROP, DISPUTE_RESOLUTION,
PENALTY_CLAUSE, UNILATERAL_TERMS, WAIVER_CLAUSE, UNKNOWN
"""

# Lương tối thiểu vùng (VNĐ/tháng) — căn cứ đại diện NĐ 38/2022 và điều chỉnh theo spec trong skill
REGIONAL_MINIMUM_WAGE: dict[str, int] = {
    "I": 4_960_000,
    "II": 4_410_000,
    "III": 3_860_000,
    "IV": 3_450_000,
}

VIOLATION_SCORE_PENALTY = {"VIOLATION": 15, "HIGH_RISK": 8, "MEDIUM_RISK": 3}
MISSING_MANDATORY_PENALTY = 5

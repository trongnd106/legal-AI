"""
query/rule_validator.py — Rule-based Validation Layer (extensible theo domain).

Validate kết quả LLM bằng các quy tắc cứng từ pháp luật.
Dễ mở rộng: thêm domain mới = thêm 1 entry vào DOMAIN_RULES.

Giá trị lương tối thiểu vùng: NĐ 74/2024/NĐ-CP (hiệu lực 01/07/2024).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid:    bool
    warnings:    list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)


# ==========================================================================
# Quy tắc theo từng lĩnh vực
# ==========================================================================
DOMAIN_RULES: dict[str, dict] = {

    "lao_dong": {
        # NĐ 74/2024/NĐ-CP, hiệu lực 01/07/2024
        "luong_toi_thieu_vung": {
            "vung_I":  4_960_000,
            "vung_II": 4_410_000,
            "vung_III":3_860_000,
            "vung_IV": 3_450_000,
        },
        "gio_lam_toi_da_ngay":   8,   # Điều 105 BLLĐ 2019
        "gio_lam_toi_da_tuan":   48,
        "them_gio_toi_da_ngay":  4,   # Điều 107 BLLĐ 2019
        "them_gio_toi_da_thang": 40,
        "them_gio_toi_da_nam":   200, # (300 với ngành đặc biệt)
        "nghi_phep_toi_thieu":   12,  # ngày/năm, Điều 113 BLLĐ 2019
    },

    "dan_su": {
        "thoi_hieu_khoi_kien_chung":          3,   # năm, Điều 429 BLDS 2015
        "thoi_hieu_yeu_cau_tuyen_vo_hieu":    2,   # năm, Điều 132 BLDS 2015
        "thoi_hieu_thua_ke":                 30,   # năm, Điều 623 BLDS 2015
        "lai_suat_cho_vay_toi_da":           20,   # %/năm, Điều 468 BLDS 2015
    },

    "hinh_su": {
        "tuoi_toi_thieu_trach_nhiem_hs": 14,  # tuổi, Điều 12 BLHS 2015
        "tuoi_day_du_trach_nhiem_hs":    16,
        "muc_tien_phat_toi_da_ca_nhan":  1_000_000_000,  # đồng
    },

    "doanh_nghiep": {
        "von_dieu_le_toi_thieu_cty_luat": 10_000_000_000,  # đồng, Luật Luật sư
        "thoi_han_gop_von_dieu_le":        90,              # ngày, Điều 47 LDN
    },

    "thue": {
        "thue_gtgt_pho_thong":           10,   # %
        "thue_gtgt_uu_dai":               5,
        "thue_thu_nhap_ca_nhan_toi_da":  35,   # %
        "thue_tndn_pho_thong":           20,   # %
    },
}


def validate_answer(
    answer: str,
    domain: str,
    question_keywords: list[str] | None = None,
) -> ValidationResult:
    """
    Kiểm tra câu trả lời LLM không vi phạm quy tắc cứng của domain.

    Parameters
    ----------
    answer:
        Câu trả lời LLM cần kiểm tra.
    domain:
        Lĩnh vực pháp luật ("lao_dong", "dan_su", "hinh_su", "doanh_nghiep", "thue").
    question_keywords:
        Từ khoá từ câu hỏi để quyết định áp dụng rule nào.

    Returns
    -------
    ValidationResult
    """
    warnings:    list[str] = []
    corrections: list[str] = []
    rules        = DOMAIN_RULES.get(domain, {})
    q_keywords   = [k.lower() for k in (question_keywords or [])]

    # -----------------------------------------------------------------------
    # Luật Lao động
    # -----------------------------------------------------------------------
    if domain == "lao_dong":
        if any(k in q_keywords for k in ["lương", "tiền lương", "lương tối thiểu"]):
            amounts = re.findall(r"(\d[\d.,]+)\s*(đồng|triệu)?", answer)
            min_iv  = rules.get("luong_toi_thieu_vung", {}).get("vung_IV", 3_450_000)
            for amt_str, unit in amounts:
                try:
                    amt = float(amt_str.replace(",", "").replace(".", ""))
                    if unit and unit.strip() == "triệu":
                        amt *= 1_000_000
                    if 100_000 < amt < min_iv:
                        warnings.append(
                            f"⚠️ Mức lương {amt:,.0f} đồng thấp hơn lương tối thiểu "
                            f"vùng IV ({min_iv:,} đồng/tháng — NĐ 74/2024/NĐ-CP)."
                        )
                except ValueError:
                    pass

        if any(k in q_keywords for k in ["giờ làm", "làm thêm", "tăng ca", "giờ"]):
            hours = re.findall(r"(\d+)\s*giờ", answer)
            max_day = (
                rules.get("gio_lam_toi_da_ngay", 8)
                + rules.get("them_gio_toi_da_ngay", 4)
            )
            for h in hours:
                if int(h) > max_day:
                    warnings.append(
                        f"⚠️ {h} giờ/ngày vượt giới hạn tối đa "
                        f"({max_day} giờ/ngày — Điều 105, 107 BLLĐ 2019)."
                    )

        if any(k in q_keywords for k in ["nghỉ phép", "phép năm"]):
            days = re.findall(r"(\d+)\s*ngày", answer)
            min_leave = rules.get("nghi_phep_toi_thieu", 12)
            for d in days:
                if 0 < int(d) < min_leave:
                    corrections.append(
                        f"ℹ️ Nghỉ phép tối thiểu là {min_leave} ngày/năm "
                        f"(Điều 113 BLLĐ 2019), không phải {d} ngày."
                    )

    # -----------------------------------------------------------------------
    # Luật Dân sự
    # -----------------------------------------------------------------------
    elif domain == "dan_su":
        if any(k in q_keywords for k in ["thời hiệu", "khởi kiện", "yêu cầu"]):
            years = re.findall(r"(\d+)\s*năm", answer)
            for y in years:
                if int(y) > 30:
                    warnings.append(
                        f"⚠️ Thời hiệu {y} năm bất thường — "
                        "thời hiệu thừa kế tối đa là 30 năm (Điều 623 BLDS 2015)."
                    )

        if any(k in q_keywords for k in ["lãi suất", "lãi", "cho vay"]):
            max_rate = rules.get("lai_suat_cho_vay_toi_da", 20)
            rates    = re.findall(r"(\d+(?:\.\d+)?)\s*%", answer)
            for r_str in rates:
                if float(r_str) > max_rate:
                    warnings.append(
                        f"⚠️ Lãi suất {r_str}%/năm vượt trần {max_rate}%/năm "
                        f"(Điều 468 BLDS 2015)."
                    )

    # -----------------------------------------------------------------------
    # Luật Hình sự
    # -----------------------------------------------------------------------
    elif domain == "hinh_su":
        if any(k in q_keywords for k in ["tuổi", "vị thành niên", "người chưa thành niên"]):
            min_age = rules.get("tuoi_toi_thieu_trach_nhiem_hs", 14)
            ages    = re.findall(r"(\d+)\s*tuổi", answer)
            for a in ages:
                if int(a) < min_age:
                    warnings.append(
                        f"⚠️ Người dưới {min_age} tuổi không chịu trách nhiệm "
                        f"hình sự (Điều 12 BLHS 2015)."
                    )

    # -----------------------------------------------------------------------
    # Luật Doanh nghiệp
    # -----------------------------------------------------------------------
    elif domain == "doanh_nghiep":
        if any(k in q_keywords for k in ["góp vốn", "vốn điều lệ"]):
            deadline = rules.get("thoi_han_gop_von_dieu_le", 90)
            days     = re.findall(r"(\d+)\s*ngày", answer)
            for d in days:
                if 0 < int(d) < deadline:
                    corrections.append(
                        f"ℹ️ Thời hạn góp đủ vốn điều lệ là {deadline} ngày "
                        f"(Điều 47 LDN 2020), không phải {d} ngày."
                    )

    return ValidationResult(
        is_valid=len(warnings) == 0 and len(corrections) == 0,
        warnings=warnings,
        corrections=corrections,
    )

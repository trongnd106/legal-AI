"""
tests/evaluation_suite.py — Bộ test cases đa lĩnh vực với ground truth.

Cách dùng:
    from tests.evaluation_suite import TEST_CASES, evaluate_system

    def my_answer_fn(question: str, domain: str) -> dict:
        # ...gọi ask_local hoặc ask_global...
        return {"answer": "...", "cited_articles": ["Điều 35", ...]}

    results = evaluate_system(my_answer_fn)
"""
from __future__ import annotations

import re

TEST_CASES: list[dict] = [

    # ===================== LUẬT LAO ĐỘNG =====================
    {
        "id": "LD001", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "easy",
        "question": "Người lao động có bao nhiêu ngày nghỉ phép năm tối thiểu?",
        "expected_keywords": ["12 ngày", "Điều 113"],
        "expected_citations": ["Điều 113"],
    },
    {
        "id": "LD002", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "easy",
        "question": "Lương tối thiểu vùng I hiện tại là bao nhiêu?",
        "expected_keywords": ["4.960.000", "vùng I"],
        "expected_citations": ["Điều 91"],
    },
    {
        "id": "LD003", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "easy",
        "question": "Thời gian thử việc tối đa đối với công việc đòi hỏi trình độ chuyên môn là bao lâu?",
        "expected_keywords": ["60 ngày", "Điều 27"],
        "expected_citations": ["Điều 27"],
    },
    {
        "id": "LD004", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "medium",
        "question": "Hợp đồng lao động không xác định thời hạn có thể ký bao nhiêu lần?",
        "expected_keywords": ["Điều 20"],
        "expected_citations": ["Điều 20"],
    },
    {
        "id": "LD010", "domain": "lao_dong",
        "category": "multi_hop", "difficulty": "medium",
        "question": "Người sử dụng lao động không trả trợ cấp thôi việc thì bị xử lý thế nào?",
        "expected_keywords": ["Điều 46", "xử phạt"],
        "expected_citations": ["Điều 46"],
        "reasoning_chain": "Điều 46 (nghĩa vụ) → NĐ 12/2022 (chế tài)",
    },
    {
        "id": "LD011", "domain": "lao_dong",
        "category": "multi_hop", "difficulty": "hard",
        "question": "NLĐ đơn phương chấm dứt đúng pháp luật có được trợ cấp thôi việc không và cần điều kiện gì?",
        "expected_keywords": ["báo trước", "Điều 35", "Điều 46"],
        "expected_citations": ["Điều 35", "Điều 46"],
        "reasoning_chain": "Điều 35 (quyền) → Điều 46 (hậu quả tài chính)",
    },
    {
        "id": "LD012", "domain": "lao_dong",
        "category": "multi_hop", "difficulty": "hard",
        "question": "Công ty trả lương dưới mức tối thiểu vùng IV thì bị phạt bao nhiêu?",
        "expected_keywords": ["NĐ 12/2022", "phạt tiền"],
        "expected_citations": [],
        "reasoning_chain": "Điều 90 (nghĩa vụ trả lương) → NĐ 12/2022 (mức phạt)",
    },
    {
        "id": "LD013", "domain": "lao_dong",
        "category": "single_hop", "difficulty": "medium",
        "question": "Người lao động được nghỉ bao nhiêu ngày khi kết hôn?",
        "expected_keywords": ["3 ngày", "Điều 115"],
        "expected_citations": ["Điều 115"],
    },

    # ===================== LUẬT DÂN SỰ =====================
    {
        "id": "DS001", "domain": "dan_su",
        "category": "single_hop", "difficulty": "easy",
        "question": "Điều kiện để giao dịch dân sự có hiệu lực là gì?",
        "expected_keywords": ["Điều 117", "năng lực hành vi", "tự nguyện"],
        "expected_citations": ["Điều 117"],
    },
    {
        "id": "DS002", "domain": "dan_su",
        "category": "single_hop", "difficulty": "easy",
        "question": "Thời hiệu khởi kiện tranh chấp hợp đồng dân sự là bao nhiêu năm?",
        "expected_keywords": ["3 năm", "Điều 429"],
        "expected_citations": ["Điều 429"],
    },
    {
        "id": "DS010", "domain": "dan_su",
        "category": "multi_hop", "difficulty": "medium",
        "question": "Hợp đồng vô hiệu do giả tạo thì hậu quả pháp lý là gì?",
        "expected_keywords": ["Điều 124", "vô hiệu", "hoàn trả"],
        "expected_citations": ["Điều 124", "Điều 131"],
        "reasoning_chain": "Điều 124 (vô hiệu giả tạo) → Điều 131 (hậu quả)",
    },
    {
        "id": "DS011", "domain": "dan_su",
        "category": "multi_hop", "difficulty": "hard",
        "question": "Lãi suất cho vay tối đa theo BLDS 2015 là bao nhiêu và vi phạm thì sao?",
        "expected_keywords": ["20%", "Điều 468"],
        "expected_citations": ["Điều 468"],
        "reasoning_chain": "Điều 468 (lãi suất) → hậu quả phần lãi vượt trần",
    },
    {
        "id": "DS012", "domain": "dan_su",
        "category": "single_hop", "difficulty": "medium",
        "question": "Điều kiện để hợp đồng vô hiệu do lừa dối là gì?",
        "expected_keywords": ["Điều 127", "lừa dối"],
        "expected_citations": ["Điều 127"],
    },

    # ===================== LUẬT HÌNH SỰ =====================
    {
        "id": "HS001", "domain": "hinh_su",
        "category": "single_hop", "difficulty": "easy",
        "question": "Người bao nhiêu tuổi thì chịu trách nhiệm hình sự?",
        "expected_keywords": ["14 tuổi", "16 tuổi", "Điều 12"],
        "expected_citations": ["Điều 12"],
    },
    {
        "id": "HS002", "domain": "hinh_su",
        "category": "single_hop", "difficulty": "medium",
        "question": "Tội cố ý gây thương tích với tỷ lệ tổn thương cơ thể từ 31% đến 60% thì hình phạt là gì?",
        "expected_keywords": ["Điều 134", "phạt tù"],
        "expected_citations": ["Điều 134"],
    },
    {
        "id": "HS010", "domain": "hinh_su",
        "category": "multi_hop", "difficulty": "hard",
        "question": "Tội lừa đảo chiếm đoạt tài sản trên 500 triệu đồng thì hình phạt tối đa là gì?",
        "expected_keywords": ["Điều 174", "phạt tù", "20 năm"],
        "expected_citations": ["Điều 174"],
    },

    # ===================== LUẬT DOANH NGHIỆP =====================
    {
        "id": "DN001", "domain": "doanh_nghiep",
        "category": "single_hop", "difficulty": "easy",
        "question": "Thủ tục đăng ký thành lập công ty TNHH gồm những bước nào?",
        "expected_keywords": ["hồ sơ", "Phòng đăng ký kinh doanh", "Điều 22"],
        "expected_citations": ["Điều 22"],
    },
    {
        "id": "DN002", "domain": "doanh_nghiep",
        "category": "single_hop", "difficulty": "medium",
        "question": "Công ty TNHH một thành viên có thể tăng vốn điều lệ bằng cách nào?",
        "expected_keywords": ["Điều 87"],
        "expected_citations": ["Điều 87"],
    },
    {
        "id": "DN010", "domain": "doanh_nghiep",
        "category": "multi_hop", "difficulty": "medium",
        "question": "Giám đốc công ty TNHH 2 thành viên có những quyền hạn gì và chịu trách nhiệm gì?",
        "expected_keywords": ["Điều 63", "quyền", "trách nhiệm", "Hội đồng thành viên"],
        "expected_citations": ["Điều 63"],
    },

    # ===================== TEMPORAL =====================
    {
        "id": "TMP001", "domain": "lao_dong",
        "category": "temporal", "difficulty": "medium",
        "question": "Nghị định quy định lương tối thiểu vùng đang có hiệu lực là nghị định nào?",
        "expected_keywords": ["74/2024"],
        "expected_citations": [],
    },
    {
        "id": "TMP002", "domain": "lao_dong",
        "category": "temporal", "difficulty": "medium",
        "question": "Nghị định 90/2019/NĐ-CP có còn hiệu lực không?",
        "expected_keywords": ["hết hiệu lực", "74/2024"],
        "expected_citations": [],
    },

    # ===================== CROSS-DOMAIN =====================
    {
        "id": "CD001",
        "domain": "cross_domain",
        "category": "cross_domain", "difficulty": "hard",
        "question": (
            "Công ty vi phạm luật lao động (không đóng BHXH) thì ngoài phạt hành chính "
            "còn có thể bị xử lý thế nào theo luật hình sự?"
        ),
        "expected_keywords": ["Điều 216", "tội trốn đóng BHXH", "hành chính"],
        "expected_citations": ["Điều 216"],
        "reasoning_chain": "NĐ 12/2022 (phạt hành chính) → Điều 216 BLHS (hình sự)",
    },
    {
        "id": "CD002",
        "domain": "cross_domain",
        "category": "cross_domain", "difficulty": "hard",
        "question": (
            "Hợp đồng lao động ký với người chưa đủ 15 tuổi có hậu quả pháp lý gì "
            "theo cả luật lao động và luật dân sự?"
        ),
        "expected_keywords": ["Điều 145", "vô hiệu", "người đại diện"],
        "expected_citations": ["Điều 145"],
        "reasoning_chain": "BLLĐ (cấm sử dụng lao động < 15 tuổi) → BLDS (hợp đồng vô hiệu)",
    },
    {
        "id": "CD003",
        "domain": "cross_domain",
        "category": "cross_domain", "difficulty": "hard",
        "question": (
            "Tranh chấp về tiền lương không trả giữa NLĐ và NSDLĐ khi khởi kiện ra toà "
            "thì thời hiệu là bao nhiêu?"
        ),
        "expected_keywords": ["1 năm", "Điều 190"],
        "expected_citations": ["Điều 190"],
        "reasoning_chain": "BLLĐ (thời hiệu tranh chấp lao động cá nhân) ≠ BLDS (3 năm chung)",
    },
]


_ABBR_MAP = {
    "bllđ":   "bộ luật lao động",
    "blds":   "bộ luật dân sự",
    "blhs":   "bộ luật hình sự",
    "nđ":     "nghị định",
    "tt":     "thông tư",
    "vbhn":   "văn bản hợp nhất",
    "bhxh":   "bảo hiểm xã hội",
}


def _normalize_for_match(text: str) -> str:
    """Chuẩn hoá text để so khớp keyword linh hoạt.

    - lowercase, trim whitespace
    - loại bỏ dấu câu (trừ chữ, số, khoảng trắng)
    - expand viết tắt pháp lý thông dụng (BLLĐ, NĐ, TT…)
    - loại bỏ các stopword có thể gây nhiễu (ngày, tháng, năm, số, kể từ…)
    - chuẩn hoá số (xóa leading zero) — trừ năm 4 chữ số
    """
    t = text.lower().strip()
    # Loại bỏ dấu câu (giữ chữ, số, khoảng trắng, /)
    t = re.sub(r'[^\w\s/]', ' ', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    # Xóa stopword gây nhiễu (từ nối ngắn, trợ động từ)
    t = re.sub(r'\b(của|và|là|hoặc|các|những|để|với|về|từ|cho|vào|được|phải|phép|đã|đang|sẽ)\b', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    # Expand viết tắt
    for abbr, full in _ABBR_MAP.items():
        t = re.sub(rf'\b{re.escape(abbr)}\b', full, t)
    # Chuẩn hoá số hiệu văn bản: "45/2019/QH14" → "2019", "12/2022/NĐ-CP" → "12/2022"
    # Giữ lại năm từ registration number để khớp keyword dạng "BLLĐ 2019"
    t = re.sub(r'\bsố\s+\d+/(\d{4})/[^\s]*', r'\1', t)
    # Chuẩn hoá số hiệu nghị định: "Nghị định 12/2022/NĐ-CP" → "Nghị định 12/2022"
    t = re.sub(r'(\d+/\d{4})/[^\s]*', r'\1', t)
    # Normalize leading zero trong số (chỉ khi có chữ số khác 0 theo sau)
    t = re.sub(r'\b0+([1-9]\d*(?:/\d+)*)\b', r'\1', t)
    return t.strip()


def evaluate_system(
    answer_fn,
    test_cases: list[dict] | None = None,
) -> dict:
    """
    Đánh giá hệ thống với bộ test cases.

    Parameters
    ----------
    answer_fn:
        Hàm nhận (question: str, domain: str) -> {"answer": str, "cited_articles": list[str]}.
    test_cases:
        Danh sách test cases. Mặc định: TEST_CASES.

    Returns
    -------
    dict với keyword_accuracy, citation_accuracy, và thống kê theo domain/category.
    """
    cases = test_cases or TEST_CASES
    results: dict = {
        "total":          len(cases),
        "keyword_hits":   0,
        "citation_hits":  0,
        "by_domain":      {},
        "by_category":    {},
        "details":        [],
    }

    for tc in cases:
        response     = answer_fn(tc["question"], tc.get("domain", ""))
        answer_raw   = response.get("answer", "")
        citations    = response.get("cited_articles", [])

        # Normalize answer để khớp keyword linh hoạt hơn
        answer_norm = _normalize_for_match(answer_raw)
        kw_hit = all(
            _normalize_for_match(kw) in answer_norm
            for kw in tc["expected_keywords"]
        )
        cite_hit = (
            not tc["expected_citations"]
            or any(
                any(exp in cite for cite in citations)
                for exp in tc["expected_citations"]
            )
        )

        for bucket_key, bucket_val in [
            ("domain", tc["domain"]),
            ("category", tc["category"]),
        ]:
            b = results[f"by_{bucket_key}"].setdefault(
                bucket_val,
                {"total": 0, "keyword_hits": 0, "citation_hits": 0},
            )
            b["total"] += 1
            if kw_hit:   b["keyword_hits"]  += 1
            if cite_hit: b["citation_hits"] += 1

        if kw_hit:   results["keyword_hits"]  += 1
        if cite_hit: results["citation_hits"] += 1

        results["details"].append({
            "id":           tc["id"],
            "domain":       tc["domain"],
            "category":     tc["category"],
            "difficulty":   tc["difficulty"],
            "kw_hit":       kw_hit,
            "cite_hit":     cite_hit,
            "question":     tc["question"],
        })

    total = results["total"]
    results["keyword_accuracy"]  = results["keyword_hits"]  / total
    results["citation_accuracy"] = results["citation_hits"] / total

    # --- Print summary ---
    print(f"\n{'='*50}")
    print(f"KẾT QUẢ ĐÁNH GIÁ  ({total} test cases)")
    print(f"{'='*50}")
    print(f"Keyword Accuracy  : {results['keyword_accuracy']:.1%}  "
          f"({results['keyword_hits']}/{total})")
    print(f"Citation Accuracy : {results['citation_accuracy']:.1%}  "
          f"({results['citation_hits']}/{total})")

    print("\nTheo Domain:")
    for domain, stats in sorted(results["by_domain"].items()):
        kw = stats["keyword_hits"] / stats["total"]
        print(f"  {domain:20s}: {kw:.1%}  ({stats['keyword_hits']}/{stats['total']})")

    print("\nTheo Category:")
    for cat, stats in sorted(results["by_category"].items()):
        kw = stats["keyword_hits"] / stats["total"]
        print(f"  {cat:15s}: {kw:.1%}  ({stats['keyword_hits']}/{stats['total']})")

    return results

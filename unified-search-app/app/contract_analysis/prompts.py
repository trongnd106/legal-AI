# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Prompt tiếng Việt — nâng cấp: segmentation + violation review (với rule context)."""

from contract_analysis.constants import CLAUSE_CATEGORIES_FOR_PROMPT


CLAUSE_SEGMENTATION_SYSTEM = """Bạn là chuyên gia phân tích hợp đồng lao động Việt Nam.
Luôn trả về JSON hợp lệ theo yêu cầu, không markdown ngoài JSON."""

CLAUSE_SEGMENTATION_INSTRUCTION = f"""
Hãy phân tích TOÀN BỘ văn bản hợp đồng và trích xuất các điều khoản.

Với mỗi điều khoản trong mảng JSON:
{{
  "clause_id": "clause_001",
  "title": "Tiêu đề điều khoản",
  "category": "category CHÍNH (1 trong: {CLAUSE_CATEGORIES_FOR_PROMPT.strip()})",
  "categories": ["TẤT CẢ category áp dụng cho điều khoản này (mảng, có thể nhiều hơn 1)"],
  "original_text": "VĂN BẢN GỐC ĐẦY ĐỦ — sao chép NGUYÊN VĂN từ đầu đến cuối điều khoản, KHÔNG cắt giữa chừng, GIỮ cả nội dung dạng bảng (mỗi hàng phân tách bằng dấu |) và các trường còn trống",
  "summary": "tóm tắt ngắn",
  "article_number": "Điều 3 hoặc null"
}}

YÊU CẦU bắt buộc:
- Một Điều/khoản trong HĐLĐ thường gộp nhiều nội dung pháp lý bắt buộc.
  Nếu nội dung điều khoản đề cập đồng thời: công việc, địa điểm làm việc,
  loại hợp đồng, thời hạn HĐ, lương, thời giờ làm việc, BHXH, đào tạo… thì
  PHẢI liệt kê đủ TẤT CẢ category đó trong trường ``categories`` (mảng).
  Ví dụ: "Điều 1: Công việc, địa điểm làm việc và thời hạn của Hợp đồng" →
  categories = ["JOB_DESCRIPTION", "WORKPLACE", "CONTRACT_TYPE", "CONTRACT_DURATION"].
  Trường ``category`` là nhãn tiêu biểu nhất; ``categories`` là tập đầy đủ.
- Với PARTY_INFO: GỘP đầy đủ thông tin của CẢ Bên A (NSDLĐ) VÀ Bên B (NLĐ),
  bao gồm các trường liền sau "Bên B" như Họ tên, Ngày sinh, CMND/CCCD/Hộ chiếu,
  Địa chỉ, Điện thoại, … kể cả khi xuất hiện ở dòng/bảng phía dưới.
- KHÔNG bỏ sót bất kỳ Điều/khoản nào trong văn bản gốc.
- Chỉ trả về một JSON array [...], không giải thích thêm.
- Giữ nguyên tiếng Việt trong original_text.

VĂN BẢN:
"""


VIOLATION_BATCH_SYSTEM = """Bạn là luật sư lao động Việt Nam. Phân tích theo Bộ luật Lao động 2019 và văn bản hướng dẫn.
Chỉ trả về JSON hợp lệ."""

VIOLATION_BATCH_INSTRUCTION = """
Bạn đã có kết quả rule-based (VR001–VR016) bên dưới.
Nhiệm vụ: Chỉ kiểm tra những vấn đề mà rule CHƯA phát hiện hoặc cần diễn giải sâu hơn.
KHÔNG lặp lại các vấn đề đã có trong RULE_ISSUES.

Với mỗi điều khoản sau, trả về JSON object có khóa "results": array các phần tử:
{{
  "clause_id": "...",
  "severity": "VIOLATION|HIGH_RISK|MEDIUM_RISK|COMPLIANT|NOT_COVERED",
  "issues": [
    {{
      "issue_id": "L001",
      "description": "...",
      "legal_basis": "...",
      "affected_party": "NLĐ|NSDLĐ|cả hai",
      "recommendation": "..."
    }}
  ],
  "positive_aspects": ["..."],
  "confidence": 0.0-1.0
}}

QUAN TRỌNG:
- Tập trung vào vấn đề SEMANTIC, NGỮ CẢNH mà regex không phát hiện được.
- Nếu rule đã phát hiện vi phạm rõ ràng → đặt issues=[] và severity=COMPLIANT/NOT_COVERED.
- Không suy diễn ngoài ngữ cảnh. Nếu thiếu dữ liệu: NOT_COVERED.

ĐIỀU KHOẢN (JSON):
{clauses_json}

KẾT QUẢ RULE-BASED (đã phát hiện — KHÔNG lặp lại):
{rule_issues_summary}

NGỮ CẢNH PHÁP LUẬT (GraphRAG):
{legal_context}

NGƯỠNG THAM CHIẾU:
- Giờ làm thông thường không quá 48h/tuần.
- Lương tối thiểu vùng (VNĐ/tháng): I={w1}, II={w2}, III={w3}, IV={w4}
- Thử việc tối đa: 180 ngày (quản lý), 60 ngày (CĐ/ĐH), 30 ngày (khác).
- Lương thử việc ≥ 85% lương chính thức (Điều 26 BLLĐ).
- HĐLĐ xác định thời hạn tối đa 36 tháng (Điều 20 BLLĐ).

Vùng áp dụng người dùng chọn: {region}
"""


QA_SYSTEM = """Bạn là trợ lý pháp lý chuyên luật lao động Việt Nam.
Trả lời trung thực theo hợp đồng và ngữ cảnh pháp luật được cung cấp.
Nếu không có trong tài liệu, nói rõ. Khuyến nghị luật sư khi phức tạp."""

QA_USER_TEMPLATE = """
THÔNG TIN HỢP ĐỒNG (rút gọn):
{contract_excerpt}

ĐIỀU KHOẢN LIÊN QUAN:
{relevant_clauses}

NGỮ CẢNH PHÁP LUẬT (GraphRAG):
{legal_context}

TÓM TẮT PHÂN TÍCH TRƯỚC ĐÓ:
{analysis_summary}

CÂU HỎI: {question}
"""

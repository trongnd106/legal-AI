"""
Convert question-benchmark.csv (simple format) to the standard rich format
matching qa_benchmark_questions.csv, with expected_keywords, expected_citations,
difficulty, category, domain, reasoning_chain, etc.

Usage:
    uv run python scripts/convert_benchmark_csv.py
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

INPUT  = Path("tests/data/question-benchmark.csv")
OUTPUT = Path("tests/data/qa_benchmark_questions.csv")

# ───────────────────────── helpers ─────────────────────────

def _fmt_citations(raw: str) -> str:
    """Normalise citation field e.g. 'Điều 3, Khoản 1' -> 'Điều 3|BLLĐ 2019'"""
    parts = re.split(r'[,;&]', raw)
    clean = [p.strip() for p in parts if p.strip()]
    return "|".join(clean) if clean else ""


def _parse_ref(ref: str) -> str:
    ref = ref.strip()
    if not ref:
        return ""
    return ref


def _kw_join(*args: str) -> str:
    return "|".join(args)


# ──────────── keyword / citation / difficulty per ID ────────────
# We define per-QID because automated extraction is unreliable.
# Each entry: (expected_keywords, expected_citations, reasoning_chain, difficulty, category)

# ───── TK ─────
TK = {
    "TK01": ("tên người sử dụng lao động|doanh nghiệp|giấy chứng nhận đăng ký doanh nghiệp", "Điều 3|Khoản 1", "", "easy", "single_hop"),
    "TK02": ("địa chỉ|hộ gia đình|chứng minh nhân dân|căn cước công dân", "Điều 3|Khoản 1", "", "easy", "single_hop"),
    "TK03": ("mức lương|đơn vị thời gian|tháng", "Điều 3|Khoản 5", "", "easy", "single_hop"),
    "TK04": ("bồi thường thiệt hại|bí mật kinh doanh", "Điều 4|Khoản 3", "", "medium", "single_hop"),
    "TK05": ("nông nghiệp|nâng bậc lương|công việc giản đơn", "Điều 5|Khoản 1", "", "medium", "single_hop"),
    "TK06": ("15 tuổi|người lao động", "Điều 3|Khoản 1", "", "easy", "single_hop"),
    "TK07": ("cưỡng bức lao động", "Điều 3|Khoản 7", "", "easy", "single_hop"),
    "TK08": ("nội quy lao động|kỷ luật lao động", "Điều 5|Khoản 2", "", "easy", "single_hop"),
    "TK09": ("người sử dụng lao động|chi trả", "Điều 11|Khoản 2", "", "easy", "single_hop"),
    "TK10": ("lời nói|dưới 01 tháng", "Điều 14|Khoản 2", "", "easy", "single_hop"),
    "TK11": ("không được giữ|bản chính|giấy tờ tùy thân", "Điều 17|Khoản 1", "", "easy", "single_hop"),
    "TK12": ("36 tháng|xác định thời hạn", "Điều 20|Khoản 1", "", "easy", "single_hop"),
    "TK13": ("60 ngày|cao đẳng|thử việc", "Điều 25|Khoản 2", "", "easy", "single_hop"),
    "TK14": ("85%|thử việc", "Điều 26", "", "easy", "single_hop"),
    "TK15": ("22 giờ|06 giờ|ban đêm", "Điều 106", "", "easy", "single_hop"),
    "TK16": ("tổ chức|gấp đôi|cá nhân", "Điều 6|Khoản 1", "", "medium", "single_hop"),
    "TK17": ("thu tiền|tuyển dụng", "Điều 8|Khoản 1", "", "medium", "single_hop"),
    "TK18": ("buộc trả lại|bản chính|văn bằng", "Điều 9|Khoản 3", "", "medium", "single_hop"),
    "TK19": ("2.000.000|5.000.000|thử việc", "Điều 10|Khoản 2", "", "medium", "single_hop"),
    "TK20": ("quấy rối tình dục|phạt tiền", "Điều 11|Khoản 3", "", "medium", "single_hop"),
    "TK21": ("tối đa|lương tối thiểu|phạt tiền", "Điều 17|Khoản 3", "", "medium", "single_hop"),
    "TK22": ("nghỉ hằng năm|phạt tiền", "Điều 18|Khoản 2", "", "medium", "single_hop"),
    "TK23": ("trục xuất|nước ngoài|giấy phép lao động", "Điều 32|Khoản 5", "", "medium", "single_hop"),
    "TK24": ("báo cáo|thay đổi lao động|định kỳ", "Điều 4|Khoản 2", "", "medium", "single_hop"),
    "TK25": ("giám đốc|vốn nhà nước|36 tháng", "Điều 5|Khoản 5", "", "medium", "single_hop"),
    "TK26": ("quản lý doanh nghiệp|báo trước|120 ngày", "Điều 7|Khoản 2", "", "medium", "single_hop"),
    "TK27": ("01 năm|tháng lẻ|06 tháng", "Điều 8|Khoản 3", "", "medium", "single_hop"),
    "TK28": ("ký quỹ|cho thuê lại", "Điều 21|Khoản 2", "", "hard", "single_hop"),
    "TK29": ("đối thoại|ít nhất|bên sử dụng lao động", "Điều 38|Khoản 1", "", "medium", "single_hop"),
    "TK30": ("lương tuần|lương tháng|nhân với 12 tháng|52 tuần", "Điều 54|Khoản 1", "", "medium", "single_hop"),
    "TK31": ("nghỉ giữa giờ|ban đêm|ca liên tục|45 phút", "Điều 64|Khoản 2", "", "medium", "single_hop"),
    "TK32": ("chuyên gia|bằng đại học|05 năm kinh nghiệm", "Điều 1|Khoản 1", "", "medium", "single_hop"),
    "TK33": ("15 ngày|báo cáo giải trình|nhu cầu", "Điều 1|Khoản 2", "", "medium", "single_hop"),
    "TK34": ("cổng thông tin điện tử|Bộ Lao động", "Điều 1|Khoản 2", "", "medium", "single_hop"),
    "TK35": ("05 ngày làm việc|chấp thuận", "Điều 1|Khoản 2", "", "medium", "single_hop"),
    "TK36": ("03 ngày|báo cáo|mạng", "Điều 1|Khoản 3", "", "medium", "single_hop"),
    "TK37": ("4.960.000|Vùng I|lương tối thiểu", "Điều 3|Khoản 1", "", "easy", "single_hop"),
    "TK38": ("22.000|Vùng III|lương tối thiểu giờ", "Điều 3|Khoản 1", "", "easy", "single_hop"),
    "TK39": ("chi nhánh|địa bàn|áp dụng mức lương", "Điều 3|Khoản 3", "", "medium", "single_hop"),
    "TK40": ("lao động làm việc|thời giờ làm việc bình thường", "Điều 4|Khoản 1", "", "medium", "single_hop"),
    "TK41": ("lương theo ngày|nhân với 243|chia 243", "Điều 4|Khoản 3", "", "hard", "single_hop"),
    "TK42": ("01 tháng 7 năm 2024|hiệu lực", "Điều 5|Khoản 1", "", "easy", "single_hop"),
    "TK43": ("01 tháng|BHXH bắt buộc|hợp đồng lao động", "Điều 2|Khoản 1", "", "easy", "single_hop"),
    "TK44": ("phương thức đóng|mức đóng|tự nguyện", "Điều 3|Khoản 4", "", "easy", "single_hop"),
    "TK45": ("ốm đau|thai sản|hưu trí|tử tuất|bảo hiểm", "Điều 4|Khoản 2", "", "easy", "single_hop"),
    "TK46": ("tiền lương|tháng đóng BHXH", "Điều 5|Khoản 2", "", "medium", "single_hop"),
    "TK47": ("tẩy xóa|sửa chữa|sổ bảo hiểm xã hội", "Điều 9|Khoản 9", "", "easy", "single_hop"),
    "TK48": ("30 ngày|ốm đau|dưới 15 năm", "Điều 43|Khoản 1", "", "medium", "single_hop"),
    "TK49": ("02 lần|mức tham chiếu|trợ cấp một lần", "Điều 58|Khoản 4", "", "medium", "single_hop"),
    "TK50": ("15 năm|lương hưu", "Điều 64|Khoản 1", "", "easy", "single_hop"),
}

# ───── TH ─────
TH = {
    "TH01": ("địa điểm làm việc|các kho bãi|nhiều địa điểm", "Điều 3|Khoản 3", "", "medium", "single_hop"),
    "TH02": ("hộ gia đình|căn cước công dân|chứng minh nhân dân", "Điều 3|Khoản 1", "", "medium", "single_hop"),
    "TH03": ("bồi thường thiệt hại|bí mật kinh doanh", "Điều 4|Khoản 3", "", "medium", "single_hop"),
    "TH04": ("nông nghiệp|nâng bậc lương|giảm nội dung", "Điều 5|Khoản 1", "", "medium", "single_hop"),
    "TH05": ("không được|lao động nữ|thợ lặn", "Điều 10|Khoản 1|Phụ lục", "", "hard", "single_hop"),
    "TH06": ("bình quân|06 tháng|tiền lương", "Điều 12|Khoản 3", "", "hard", "single_hop"),
    "TH07": ("người đại diện theo pháp luật|16 tuổi|giao kết", "Điều 18|Khoản 4", "", "medium", "single_hop"),
    "TH08": ("không xác định thời hạn|30 ngày", "Điều 20|Khoản 2", "", "medium", "single_hop"),
    "TH09": ("60 ngày|cao đẳng|thử việc", "Điều 25|Khoản 2", "", "easy", "single_hop"),
    "TH10": ("03 ngày làm việc|báo trước|hỏa hoạn", "Điều 29|Khoản 2", "", "medium", "single_hop"),
    "TH11": ("không được yêu cầu|nuôi con dưới 12 tháng|làm thêm giờ", "Điều 137|Khoản 1", "", "easy", "single_hop"),
    "TH12": ("đã nghỉ hưu|nhiều lần|xác định thời hạn", "Điều 149|Khoản 1", "", "medium", "single_hop"),
    "TH13": ("từ chối|nguy hiểm|máy móc", "Điều 5|Khoản 1", "", "easy", "single_hop"),
    "TH14": ("500.000|phỏng vấn|thu tiền", "Điều 8|Khoản 1", "", "medium", "single_hop"),
    "TH15": ("nội quy lao động|văn bản|phạt", "Điều 19|Khoản 2", "", "medium", "single_hop"),
    "TH16": ("quấy rối tình dục|phạt tiền|tối đa", "Điều 11|Khoản 3", "", "medium", "single_hop"),
    "TH17": ("trả đủ|tiền lương cộng lãi|khắc phục hậu quả", "Điều 17|Khoản 5", "", "medium", "single_hop"),
    "TH18": ("trục xuất|nước ngoài|giấy phép", "Điều 32|Khoản 5", "", "medium", "single_hop"),
    "TH19": ("giấy phép giả|nộp lại|cho thuê lại", "Điều 13|Khoản 7|Khoản 9", "", "hard", "single_hop"),
    "TH20": ("01 năm|lẻ 8 tháng|trợ cấp thôi việc", "Điều 8|Khoản 3", "", "medium", "single_hop"),
    "TH21": ("bên thuê lại|không thấp hơn|nhân viên chính thức", "Điều 14|Điều 56", "Điều 14 NĐ 145/2020 → Điều 56 BLLĐ 2019 (nguyên tắc đối xử bình đẳng)", "hard", "multi_hop"),
    "TH22": ("50%|đại diện|đối thoại", "Điều 39|Khoản 4", "", "medium", "single_hop"),
    "TH23": ("45 phút|nghỉ giữa giờ|ban đêm", "Điều 64|Khoản 2", "", "medium", "single_hop"),
    "TH24": ("tháng 10|chưa nghỉ hằng năm|tiền lương", "Điều 67|Khoản 3", "", "hard", "single_hop"),
    "TH25": ("phòng vắt sữa|nhà trẻ|lao động nữ", "Điều 80|Khoản 5", "", "easy", "single_hop"),
    "TH26": ("bất kỳ lúc nào|giúp việc gia đình|chấm dứt", "Điều 89|Khoản 1", "", "easy", "single_hop"),
    "TH27": ("chuyên gia|bằng đại học|05 năm kinh nghiệm", "Điều 1|Khoản 1", "", "medium", "single_hop"),
    "TH28": ("03 ngày|báo cáo qua mạng|Sở Lao động", "Điều 1|Khoản 3", "", "medium", "single_hop"),
    "TH29": ("báo cáo giải trình|15 ngày|trước", "Điều 1|Khoản 2", "", "medium", "single_hop"),
    "TH30": ("cổng thông tin điện tử|Bộ Lao động", "Điều 1|Khoản 2", "", "medium", "single_hop"),
    "TH31": ("giám đốc điều hành|người đứng đầu|văn phòng đại diện", "Điều 1|Khoản 1", "", "hard", "single_hop"),
    "TH32": ("giấy phép mới|hồ sơ|gia hạn", "Điều 1|Khoản 7", "", "hard", "single_hop"),
    "TH33": ("Long Khánh|Đồng Nai|Vùng II|lương tối thiểu", "Điều 3|Khoản 1|Phụ lục", "", "medium", "single_hop"),
    "TH34": ("chi nhánh|địa bàn|mức lương vùng", "Điều 3|Khoản 3", "", "medium", "single_hop"),
    "TH35": ("Trà Vinh|Vùng II|22.000|lương tối thiểu giờ", "Điều 3|Khoản 1|Phụ lục", "", "medium", "single_hop"),
    "TH36": ("lương khoán|quy đổi|tháng|giờ", "Điều 4|Khoản 3", "", "hard", "single_hop"),
    "TH37": ("không được cắt giảm|phụ cấp độc hại|cao hơn", "Điều 5|Khoản 3", "", "medium", "single_hop"),
    "TH38": ("khu công nghiệp|giáp ranh|áp dụng vùng", "Điều 3|Khoản 3", "", "hard", "single_hop"),
    "TH39": ("01 tháng|không thuộc|BHXH bắt buộc", "Điều 2|Khoản 1", "", "medium", "single_hop"),
    "TH40": ("part-time|cao hơn|tham chiếu|đóng BHXH", "Điều 2|Khoản 1", "", "medium", "single_hop"),
    "TH41": ("giúp việc gia đình|không thuộc|BHXH bắt buộc", "Điều 2|Khoản 7", "", "medium", "single_hop"),
    "TH42": ("sinh đôi|02 lần|mức tham chiếu|trợ cấp một lần", "Điều 58|Khoản 4", "", "easy", "single_hop"),
    "TH43": ("30 ngày|ốm đau|10 năm", "Điều 43|Khoản 1", "", "medium", "single_hop"),
    "TH44": ("07 ngày|sinh mổ|dưỡng sức", "Điều 60|Khoản 2", "", "medium", "single_hop"),
    "TH45": ("giảm tỷ lệ|nghỉ hưu sớm|trước tuổi", "Điều 66|Khoản 3|Điều 140", "Điều 66 (cách tính lương hưu) → Điều 140 (quy định chuyển tiếp)", "hard", "multi_hop"),
}

# ───── SL ─────
SL = {
    "SL01": ("4.960.000|01 tháng|không|BHXH bắt buộc", "NĐ 74/2024|Luật BHXH|Điều 2", "NĐ 74/2024 (lương tối thiểu Vùng I) → Luật BHXH Điều 2 (điều kiện đóng BHXH)", "hard", "multi_hop"),
    "SL02": ("Thái Bình|Vùng II|giữ bản chính|phạt tiền", "NĐ 74/2024|NĐ 12/2022", "NĐ 74/2024 (lương vùng II) → NĐ 12/2022 (xử phạt giữ bản chính)", "hard", "multi_hop"),
    "SL03": ("lặn biển|nặng nhọc|40 ngày|ốm đau", "Thông tư 10/2020|Luật BHXH|Điều 43", "Thông tư 10/2020 (danh mục nghề) → Luật BHXH Điều 43 (chế độ ốm đau)", "hard", "multi_hop"),
    "SL04": ("không được|nuôi con 10 tháng|phạt tiền|NĐ 12/2022", "Thông tư 10/2020|NĐ 12/2022", "TT 10/2020 (cấm lao động nữ mang thai làm việc nặng) → NĐ 12/2022 (xử phạt)", "hard", "multi_hop"),
    "SL05": ("Vùng III|làm thêm giờ|Quốc khánh|lương tối thiểu", "NĐ 74/2024|BLLĐ 2019|Điều 98", "NĐ 74/2024 (lương Vùng III) → BLLĐ Điều 98 (lương làm thêm ngày lễ)", "hard", "multi_hop"),
    "SL06": ("15 lao động|bắt buộc|nội quy lao động|hội nghị người lao động", "BLLĐ 2019|NĐ 145/2020", "BLLĐ Điều 118 (nội quy lao động) → NĐ 145/2020 (hội nghị NLĐ)", "medium", "multi_hop"),
    "SL07": ("nước ngoài|15 tháng|BHXH|giấy phép lao động", "Luật BHXH|BLLĐ 2019", "Luật BHXH (đối tượng tham gia) → BLLĐ (thời hạn HĐLĐ với người nước ngoài)", "hard", "multi_hop"),
    "SL08": ("hầm mỏ|nặng nhọc|hết thời hạn|ốm đau dài ngày", "Thông tư 10/2020|Luật BHXH", "Danh mục nghề (TT 10/2020) → Luật BHXH (trợ cấp ốm đau cho nghề nặng nhọc)", "hard", "multi_hop"),
    "SL09": ("cho thuê lại|niêm yết|thu hồi giấy phép|phạt tiền", "NĐ 12/2022|NĐ 145/2020", "NĐ 145/2020 (niêm yết giấy phép) → NĐ 12/2022 (xử phạt, thu hồi)", "hard", "multi_hop"),
    "SL10": ("giúp việc gia đình|không đóng BHXH|trả cùng lương", "BLLĐ 2019|NĐ 145/2020", "BLLĐ 2019 (loại trừ giúp việc gia đình khỏi BHXH) → NĐ 145/2020 (khoản tiền thay thế)", "hard", "multi_hop"),
    "SL11": ("Vùng I|lương tối thiểu|8 ngày|chưa nghỉ hằng năm", "NĐ 74/2024|NĐ 145/2020|BLLĐ 2019|Điều 113|Điều 67", "NĐ 74/2024 (lương Vùng I) → NĐ 145/2020 Điều 67 (cách tính lương ngày chưa nghỉ phép)", "hard", "multi_hop"),
    "SL12": ("chuyên gia nước ngoài|thông báo|Cổng thông tin|15 ngày", "NĐ 70/2023|BLLĐ 2019", "NĐ 70/2023 (thủ tục thông báo + giải trình) → BLLĐ (nguyên tắc tuyển dụng)", "hard", "multi_hop"),
    "SL13": ("nam|vợ sinh đôi|phẫu thuật|nghỉ|trợ cấp một lần", "Luật BHXH|BLLĐ 2019", "Luật BHXH (chế độ thai sản cho nam) → BLLĐ (nghỉ việc)", "medium", "multi_hop"),
    "SL14": ("trợ cấp thôi việc|5 năm 7 tháng|phụ cấp độc hại|bình quân 6 tháng", "NĐ 145/2020|TT 10/2020", "NĐ 145/2020 Điều 8 (cách tính) → TT 10/2020 (nội dung tiền lương)", "hard", "multi_hop"),
    "SL15": ("Vùng IV|5 lao động|thấp hơn|phạt tối đa|tổ chức", "NĐ 74/2024|NĐ 12/2022", "NĐ 74/2024 (lương Vùng IV) → NĐ 12/2022 Điều 17 (mức phạt)", "hard", "multi_hop"),
    "SL16": ("mang thai|lò phản ứng|không được|thời giờ làm việc", "TT 10/2020|BLLĐ 2019|NĐ 145/2020", "TT 10/2020 (cấm lao động nữ mang thai) → BLLĐ + NĐ 145/2020 (nghĩa vụ về thời giờ làm việc)", "hard", "multi_hop"),
    "SL17": ("cho thuê lại|thay đổi trụ sở|cấp lại giấy phép|báo cáo", "NĐ 145/2020|NĐ 12/2022", "NĐ 145/2020 (thủ tục cấp lại phép) → NĐ 12/2022 (xử phạt không báo cáo)", "hard", "multi_hop"),
    "SL18": ("05 ngày|tự ý nghỉ|đơn phương chấm dứt|không trả trợ cấp thôi việc", "BLLĐ 2019|Điều 36|Điều 46|NĐ 145/2020", "BLLĐ Điều 36 (quyền chấm dứt) → Điều 46 + NĐ 145/2020 (trợ cấp thôi việc)", "hard", "multi_hop"),
    "SL19": ("1.200 lao động nữ|phòng vắt sữa|nhà trẻ|phạt tiền", "NĐ 145/2020|NĐ 12/2022", "NĐ 145/2020 Điều 80 (trang thiết bị) → NĐ 12/2022 (xử phạt)", "hard", "multi_hop"),
    "SL20": ("giấy phép|TP.HCM|Bình Dương|báo cáo|qua mạng", "NĐ 70/2023|BLLĐ 2019", "NĐ 70/2023 (báo cáo khi làm việc nhiều tỉnh) → BLLĐ (quản lý lao động nước ngoài)", "medium", "multi_hop"),
    "SL21": ("hỏa hoạn|chuyển công việc|45 ngày|lương thấp hơn|báo trước", "BLLĐ 2019|NĐ 145/2020|NĐ 12/2022", "BLLĐ Điều 29 (chuyển công việc) → NĐ 145/2020 → NĐ 12/2022 (xử phạt)", "hard", "multi_hop"),
    "SL22": ("Hội đồng thương lượng tập thể|UBND|Sở Lao động", "TT 10/2020|BLLĐ 2019", "TT 10/2020 (quy trình thành lập HĐTL) → BLLĐ (thương lượng tập thể)", "hard", "multi_hop"),
    "SL23": ("nam|36 năm|nghỉ hưu 2026|lương hưu|trợ cấp một lần", "Luật BHXH|BLLĐ 2019", "Luật BHXH (cách tính lương hưu cho nam/nữ) → BLLĐ (tuổi nghỉ hưu)", "hard", "multi_hop"),
    "SL24": ("dịch vụ việc làm|thu tiền|thông tin sai|phạt tối đa|khắc phục hậu quả", "NĐ 12/2022|BLLĐ 2019", "NĐ 12/2022 (các hành vi vi phạm) → BLLĐ (nguyên tắc)", "hard", "multi_hop"),
    "SL25": ("đối thoại định kỳ|thang lương|50% thành viên|công bố thông tin", "NĐ 145/2020|BLLĐ 2019|NĐ 74/2024", "NĐ 74/2024 (lương mới) → NĐ 145/2020 (điều kiện đối thoại) → BLLĐ", "hard", "multi_hop"),
    "SL26": ("trở lại làm việc sớm|04 tháng|thai sản|đồng ý|BHXH", "BLLĐ 2019|Luật BHXH|NĐ 145/2020", "BLLĐ (quyền trở lại làm việc sớm) → Luật BHXH (quyền lợi) → NĐ 145/2020", "hard", "multi_hop"),
    "SL27": ("tạm đình chỉ|15 ngày|50% lương|đóng BHXH", "BLLĐ 2019|NĐ 145/2020|Luật BHXH", "BLLĐ (quyền tạm đình chỉ) → NĐ 145/2020 (mức lương) → Luật BHXH", "hard", "multi_hop"),
    "SL28": ("cho thuê lại|không đóng BHXH|ký quỹ|can thiệp|60 ngày", "NĐ 145/2020|NĐ 12/2022", "NĐ 145/2020 (ký quỹ) → NĐ 12/2022 (can thiệp khi đến hạn)", "hard", "multi_hop"),
    "SL29": ("ca liên tục|ban đêm|22h|06h|nghỉ giữa giờ|45 phút|thêm tiền", "BLLĐ 2019|NĐ 145/2020|NĐ 12/2022", "BLLĐ Điều 106 (ban đêm) → NĐ 145/2020 (nghỉ giữa giờ) → NĐ 12/2022 (chế tài)", "hard", "multi_hop"),
    "SL30": ("dịch vụ đưa người lao động|thu tiền sai|đình chỉ", "NĐ 12/2022|BLLĐ 2019", "NĐ 12/2022 (xử phạt) → BLLĐ (dịch vụ việc làm)", "hard", "multi_hop"),
    "SL31": ("chết|tai nạn lao động|mai táng|tuất|BHXH", "Luật BHXH|BLLĐ 2019", "Luật BHXH (tử tuất, mai táng) → BLLĐ (tai nạn lao động)", "hard", "multi_hop"),
    "SL32": ("chia tách|mất việc|phương án sử dụng lao động|trợ cấp mất việc", "BLLĐ 2019|NĐ 145/2020", "BLLĐ Điều 42, 47 (mất việc) → NĐ 145/2020 (chi tiết)", "hard", "multi_hop"),
    "SL33": ("bí mật kinh doanh|bồi thường|khấu trừ tiền lương", "TT 10/2020|BLLĐ 2019|NĐ 145/2020", "TT 10/2020 (thỏa thuận bảo mật) → BLLĐ + NĐ 145/2020 (xử lý)", "hard", "multi_hop"),
    "SL34": ("Vùng I|Vùng III|Vùng IV|phụ cấp|không được cắt giảm", "NĐ 74/2024|BLLĐ 2019", "NĐ 74/2024 (cách áp dụng theo vùng) → BLLĐ (nguyên tắc không giảm phụ cấp)", "hard", "multi_hop"),
    "SL35": ("BHXH tự nguyện|05 tháng|đóng một lần|ngay khi đóng", "Luật BHXH|BLLĐ 2019", "Luật BHXH (đóng một lần cho thời gian còn thiếu) → BLLĐ (tuổi nghỉ hưu)", "hard", "multi_hop"),
}

# ───── TQ ─────
TQ = {
    "TQ01": ("chính sách|việc làm|đào tạo|bảo vệ|quyền", "BLLĐ 2019|Điều 4", "", "medium", "comparative"),
    "TQ02": ("hợp đồng lao động|thỏa ước|nội quy|ưu tiên", "BLLĐ 2019", "", "hard", "comparative"),
    "TQ03": ("bảo vệ bí mật|kinh doanh|công nghệ|bồi thường", "TT 10/2020", "", "medium", "comparative"),
    "TQ04": ("Hội đồng thương lượng tập thể|nhiều doanh nghiệp|đề nghị|thành lập", "TT 10/2020", "", "hard", "comparative"),
    "TQ05": ("biện pháp khắc phục hậu quả|buộc trả|buộc khôi phục", "NĐ 12/2022", "", "medium", "comparative"),
    "TQ06": ("xử phạt|trả lương|thấp hơn|làm thêm giờ|ban đêm", "NĐ 12/2022", "", "medium", "comparative"),
    "TQ07": ("sổ quản lý lao động|báo cáo định kỳ|thay đổi lao động", "NĐ 145/2020", "", "medium", "comparative"),
    "TQ08": ("lao động nữ|phòng vắt sữa|nhà trẻ|chăm sóc sức khỏe", "NĐ 145/2020", "", "easy", "comparative"),
    "TQ09": ("BHXH|bắt buộc|tự nguyện|hưu trí bổ sung|trợ cấp hưu trí", "Luật BHXH", "", "medium", "comparative"),
    "TQ10": ("đối tượng|BHXH bắt buộc|quản lý doanh nghiệp|không trọn thời gian", "Luật BHXH|Điều 2", "", "medium", "comparative"),
    "TQ11": ("BHXH một lần|điều kiện|ra nước ngoài|đủ tuổi", "Luật BHXH", "", "medium", "comparative"),
    "TQ12": ("quỹ BHXH|nguồn hình thành|đầu tư|an toàn", "Luật BHXH", "", "hard", "comparative"),
    "TQ13": ("chuyên gia nước ngoài|thông báo|giải trình|giấy phép lao động", "NĐ 70/2023", "", "medium", "comparative"),
    "TQ14": ("lương tối thiểu|4 vùng|74/2024|áp dụng theo địa bàn", "BLLĐ 2019|NĐ 74/2024", "", "medium", "comparative"),
    "TQ15": ("làm thêm giờ|giới hạn|đồng ý|tiền lương|ngày thường|ngày nghỉ|ban đêm", "BLLĐ 2019|NĐ 145/2020", "", "hard", "comparative"),
    "TQ16": ("quấy rối tình dục|nội quy|xử phạt", "BLLĐ 2019|NĐ 145/2020|NĐ 12/2022", "", "medium", "comparative"),
    "TQ17": ("cho thuê lại lao động|cấp phép|ký quỹ|công việc", "NĐ 145/2020|BLLĐ 2019", "", "hard", "comparative"),
    "TQ18": ("thai sản|nghỉ|trợ cấp một lần|trợ cấp tháng|nam|nữ", "BLLĐ 2019|Luật BHXH", "", "medium", "comparative"),
    "TQ19": ("lao động nước ngoài|điều kiện|báo cáo nhu cầu|xác nhận", "BLLĐ 2019|NĐ 70/2023", "", "medium", "comparative"),
    "TQ20": ("hưu trí|tuổi nghỉ hưu|lộ trình|bình quân tiền lương", "BLLĐ 2019|Luật BHXH", "", "hard", "comparative"),
    "TQ21": ("kỷ luật lao động|trình tự|xử phạt|xâm phạm thân thể|nhân phẩm", "BLLĐ 2019|NĐ 12/2022", "", "medium", "comparative"),
    "TQ22": ("đối thoại|dân chủ|cơ sở|bắt buộc|số lượng|thành phần", "BLLĐ 2019|NĐ 145/2020", "", "medium", "comparative"),
    "TQ23": ("chấm dứt|trợ cấp thôi việc|trợ cấp mất việc|thời gian làm việc", "BLLĐ 2019|NĐ 145/2020", "", "medium", "comparative"),
    "TQ24": ("chậm đóng|trốn đóng|BHXH|phạt|lãi", "Luật BHXH|NĐ 12/2022", "", "medium", "comparative"),
    "TQ25": ("lao động yếu thế|nặng nhọc|độc hại|chưa thành niên|khuyết tật", "TT 10/2020|BLLĐ 2019", "", "medium", "comparative"),
}

# ───── HL ─────
HL = {
    "HL01": ("01 tháng 1 năm 2021|hiệu lực|BLLĐ 2019", "Điều 220|Khoản 1", "", "easy", "temporal"),
    "HL02": ("hết hiệu lực|thay thế|BLLĐ 2012", "Điều 220|Khoản 1", "", "easy", "temporal"),
    "HL03": ("tiếp tục thực hiện|thuận lợi hơn|người lao động", "Điều 220|Khoản 2", "", "easy", "temporal"),
    "HL04": ("kể từ ngày ký kết|không thỏa thuận", "Điều 78|Khoản 1", "", "medium", "temporal"),
    "HL05": ("01 năm|03 năm|thỏa ước lao động tập thể", "Điều 78|Khoản 3", "", "medium", "temporal"),
    "HL06": ("60 ngày|thỏa ước cũ|thương lượng", "Điều 83", "", "medium", "temporal"),
    "HL07": ("15 ngày|nội quy lao động|đăng ký", "Điều 121", "", "medium", "temporal"),
    "HL08": ("người sử dụng lao động|tự quyết định|dưới 10 lao động", "Điều 121", "", "medium", "temporal"),
    "HL09": ("01 tháng 1 năm 2021|hiệu lực|Thông tư 10/2020", "Điều 12|Khoản 1", "", "easy", "temporal"),
    "HL10": ("Thông tư 26/2013|hết hiệu lực|lao động nữ", "Điều 12|Khoản 2", "", "medium", "temporal"),
    "HL11": ("17 tháng 1 năm 2022|hiệu lực|NĐ 12/2022", "Điều 62|Khoản 1", "", "easy", "temporal"),
    "HL12": ("luật mới|nhẹ hơn|áp dụng hồi tố", "Điều 63", "", "hard", "temporal"),
    "HL13": ("01 tháng 2 năm 2021|hiệu lực|NĐ 145/2020", "Điều 114|Khoản 1", "", "easy", "temporal"),
    "HL14": ("01 tháng 02 năm 2021|đã cấp phép|tiếp tục", "Điều 114|Khoản 3", "", "medium", "temporal"),
    "HL15": ("hết nhiệm kỳ|hòa giải viên|đã bổ nhiệm", "Điều 114|Khoản 6", "", "medium", "temporal"),
    "HL16": ("01 tháng 3 năm 2023|hiệu lực|NĐ 70/2023", "Điều 3|Khoản 1", "", "easy", "temporal"),
    "HL17": ("01 tháng 3 năm 2023|thông báo tuyển dụng|cổng thông tin", "Điều 1|Khoản 2", "", "medium", "temporal"),
    "HL18": ("NĐ 38/2022|hết hiệu lực|74/2024", "Điều 5|Khoản 2", "", "easy", "temporal"),
    "HL19": ("không được cắt giảm|bồi dưỡng bằng hiện vật|đã thỏa thuận", "Điều 5|Khoản 3", "", "medium", "temporal"),
    "HL20": ("01 tháng 7 năm 2025|hiệu lực|Luật BHXH 2024", "Điều 140|Khoản 1", "", "easy", "temporal"),
    "HL21": ("01 tháng 1 năm 2026|sổ BHXH điện tử|cấp", "Điều 25|Khoản 2", "", "medium", "temporal"),
    "HL22": ("01 tháng 7 năm 2026|giao dịch điện tử|BHXH", "Điều 26|Khoản 3", "", "medium", "temporal"),
    "HL23": ("31 tháng 12 năm 2025|ủy quyền|lương hưu|trợ cấp", "Điều 141|Khoản 14", "", "hard", "temporal"),
    "HL24": ("Luật BHXH 2024|nợ đóng|chuyển tiếp", "Điều 141|Khoản 12", "", "hard", "temporal"),
    "HL25": ("01 tháng 7 năm 2026|phá sản|phục hồi", "Điều 140|Ghi chú", "", "hard", "temporal"),
}

# ───── NP ─────
NP = {
    "NP01": ("03 cổ đông|không giới hạn|cổ đông sáng lập", "Luật Doanh nghiệp", "", "easy", "out_of_scope"),
    "NP02": ("90 ngày|góp vốn|điều lệ", "Luật Doanh nghiệp", "", "medium", "out_of_scope"),
    "NP03": ("công ty hợp danh|chịu trách nhiệm vô hạn", "Luật Doanh nghiệp", "", "medium", "out_of_scope"),
    "NP04": ("không bắt buộc|ủy quyền|đại diện", "Luật Doanh nghiệp", "", "medium", "out_of_scope"),
    "NP05": ("ngành nghề có điều kiện|đáp ứng điều kiện|cơ quan quản lý", "Luật Đầu tư", "", "medium", "out_of_scope"),
    "NP06": ("ma túy|mại dâm|vũ khí", "Luật Đầu tư", "", "easy", "out_of_scope"),
    "NP07": ("nhà đầu tư nước ngoài|tỷ lệ sở hữu|hạn chế tiếp cận thị trường", "Luật Đầu tư", "", "medium", "out_of_scope"),
    "NP08": ("điều kiện|góp vốn|mua cổ phần|nước ngoài", "Luật Đầu tư", "", "hard", "out_of_scope"),
    "NP09": ("18 tuổi|năng lực hành vi dân sự|đầy đủ", "Bộ luật Dân sự|Điều 19", "", "easy", "out_of_scope"),
    "NP10": ("bất cứ lúc nào|báo trước|03 tháng|vay không kỳ hạn", "Bộ luật Dân sự|Điều 469", "", "medium", "out_of_scope"),
    "NP11": ("vô hiệu|không có hiệu lực|hoàn trả cho nhau", "Bộ luật Dân sự", "", "medium", "out_of_scope"),
    "NP12": ("03 năm|thời hiệu khởi kiện|hợp đồng dân sự", "Bộ luật Dân sự|Điều 429", "", "medium", "out_of_scope"),
    "NP13": ("đủ 18 tuổi|hạng A1|xe mô tô", "Luật Giao thông", "", "easy", "out_of_scope"),
    "NP14": ("khoảng cách an toàn|tốc độ|thời tiết", "Luật Giao thông", "", "medium", "out_of_scope"),
    "NP15": ("nghiêm cấm|nồng độ cồn|0", "Luật Giao thông", "", "easy", "out_of_scope"),
    "NP16": ("vạch kẻ đường|vỉa hè|ưu tiên", "Luật Giao thông", "", "easy", "out_of_scope"),
    "NP17": ("sở hữu toàn dân|Nhà nước đại diện|chủ sở hữu", "Luật Đất đai", "", "easy", "out_of_scope"),
    "NP18": ("bồi thường|trước năm 1993|sử dụng ổn định", "Luật Đất đai", "", "medium", "out_of_scope"),
    "NP19": ("8%|phạt vi phạm hợp đồng|thương mại", "Luật Thương mại|Điều 301", "", "medium", "out_of_scope"),
    "NP20": ("bất khả kháng|miễn trách nhiệm|bão|lũ", "Luật Thương mại", "", "medium", "out_of_scope"),
}


# ──────────── source file short names ────────────
DOC_MAP = {
    "Thông tư 10/2020/TT-BLĐTBXH": "TT_10_2020.txt",
    "Bộ luật Lao động 2019": "BLLĐ_2019.txt",
    "Nghị định 12/2022/NĐ-CP": "ND_12_2022.txt",
    "Nghị định 145/2020/NĐ-CP": "ND_145_2020.txt",
    "Nghị định 70/2023/NĐ-CP": "ND_70_2023.txt",
    "Nghị định 74/2024/NĐ-CP": "ND_74_2024.txt",
    "Văn bản hợp nhất Luật Bảo hiểm xã hội": "VBHN_BHXH.txt",
    "Luật BHXH": "VBHN_BHXH.txt",
    "Luật Bảo hiểm xã hội (VBHN)": "VBHN_BHXH.txt",
    "Luật Bảo hiểm xã hội": "VBHN_BHXH.txt",
    "Luật Doanh nghiệp": "N/A — BLDN chưa được index",
    "Luật Đầu tư": "N/A — Luật Đầu tư chưa được index",
    "Bộ luật Dân sự": "N/A — BLDS chưa được index",
    "Luật Dân sự": "N/A — BLDS chưa được index",
    "Luật Giao thông": "N/A — Luật GT chưa được index",
    "Luật Giao thông đường bộ": "N/A — Luật GT chưa được index",
    "Luật Đất đai": "N/A — Luật ĐĐ chưa được index",
    "Luật Thương mại": "N/A — Luật TM chưa được index",
}

TYPE_MAP = {
    "TK": TK, "TH": TH, "SL": SL,
    "TQ": TQ, "HL": HL, "NP": NP,
}

DOMAIN_MAP = {
    "TK": "lao_dong", "TH": "lao_dong", "SL": "lao_dong",
    "TQ": "lao_dong", "HL": "lao_dong", "NP": "out_of_scope",
}

SEARCH_MODE = {
    "TK": "local_search", "TH": "local+multihop",
    "SL": "local+multihop", "TQ": "global_search",
    "HL": "local+temporal_filter", "NP": "should_refuse",
}

# ──────────── main conversion ────────────

def main():
    rows = []
    with open(INPUT, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stt = row["STT"].strip()
            loai = row["Loại"].strip()
            ma = row["Mã"].strip()
            question = row["Câu hỏi"].strip()
            file_raw = row["File"].strip()
            ref_raw = row["Tham chiếu"].strip() if row.get("Tham chiếu") else ""
            source_short = DOC_MAP.get(file_raw, file_raw)

            # look up per-id data
            id_map = TYPE_MAP.get(loai, {})
            if ma in id_map:
                kw_str, cite_str, rchain, diff, cat = id_map[ma]
            else:
                kw_str, cite_str, rchain, diff, cat = "", "", "", "medium", "single_hop"

            domain = DOMAIN_MAP.get(loai, "lao_dong")
            search_mode = SEARCH_MODE.get(loai, "local_search")

            in_corpus = "no" if domain == "out_of_scope" else "yes"
            count_main = "no" if domain == "out_of_scope" else "yes"

            # Build reference answer hint
            if cite_str:
                ref_answer = f"Câu trả lời cần có các từ khóa: {kw_str.replace('|', ', ')} và trích dẫn {cite_str.replace('|', ', ')}."
            else:
                ref_answer = f"Câu trả lời cần có các từ khóa: {kw_str.replace('|', ', ')}."

            # Domain note for NP
            domain_note = ""
            if loai == "NP":
                domain_note = f"Negative case: domain {file_raw}, không nằm trong corpus"

            rows.append({
                "id": ma,
                "loai_cau_hoi": loai,
                "nhan_ky_thuat": cat,
                "difficulty": diff,
                "domain": domain,
                "search_mode_khuyen_nghi": search_mode,
                "question": question,
                "expected_keywords": kw_str,
                "expected_citations": cite_str,
                "reasoning_chain": rchain,
                "reference_answer": ref_answer,
                "in_corpus": in_corpus,
                "count_main_metrics": count_main,
                "source_van_ban": source_short,
                "notes": domain_note,
            })

    # Write output
    fieldnames = [
        "id", "loai_cau_hoi", "nhan_ky_thuat", "difficulty", "domain",
        "search_mode_khuyen_nghi", "question", "expected_keywords",
        "expected_citations", "reasoning_chain", "reference_answer",
        "in_corpus", "count_main_metrics", "source_van_ban", "notes",
    ]
    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Stats
    counts = {}
    for r in rows:
        loai = r["loai_cau_hoi"]
        counts[loai] = counts.get(loai, 0) + 1
    print(f"✅ Converted {len(rows)} rows → {OUTPUT}")
    print(f"   Breakdown: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()

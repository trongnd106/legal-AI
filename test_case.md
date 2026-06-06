### 1. Run query
Với global search:
```bash
graphrag query "..." --root data/labor-law --method global
```
Với local search:
```bash
graphrag query "..." --root data/labor-law --method local
```

### 2. Câu hỏi thông thường
#### 2.1. Global Search

| ID | Câu hỏi | Tiêu chí đánh giá |
|-----|--------------|-------------|
| G01 | Các quyền và nghĩa vụ cơ bản của người lao động và người sử dụng lao động theo Bộ luật Lao động là gì? | Liệt kê đủ 2 chủ thể; có quyền/nghĩa vụ đại diện (lương, nghỉ, AT-VSLĐ) |
| G02 | Những hình thức xử lý kỷ luật lao động nào được quy định và điều kiện áp dụng ra sao? | Nêu được khiển trách, cảnh cáo, sa thải…; có điều kiện/thủ tục |
| G03 | Chế độ bảo hiểm xã hội bắt buộc đối với người lao động gồm những loại nào? | BHXH, BHYT, BHTN; ai phải đóng, ai chi trả |
| G04 | Quy định về thời gian làm việc, nghỉ giữa ca và nghỉ hằng tuần như thế nào? | Giới hạn giờ làm; nghỉ tuần; làm thêm giờ (nếu có) |
| G05 | Các nguyên tắc trả lương và thời hạn trả lương theo pháp luật lao động? | Trả đúng hạn, đúng mức; hình thức trả; không trừ lương trái luật |

#### 2.2. Local Search

| ID | Câu hỏi | Tiêu chí đánh giá |
|-----|--------------|-------------|
| L01 | CĐiều nào quy định về hợp đồng lao động không xác định thời hạn? | Trích đúng Điều; nêu điều kiện ký HĐLĐ không xác định thời hạn |
| L02 | Người lao động được nghỉ phép năm bao nhiêu ngày? | Số ngày nghỉ; điều kiện hưởng; thời điểm được nghỉ |
| L03 | Trường hợp nào người sử dụng lao động được đơn phương chấm dứt hợp đồng lao động mà không báo trước? | Liệt kê đủ các trường hợp theo luật; không nhầm với NLĐ chấm dứt |
| L04 | Mức lương tối thiểu vùng được áp dụng như thế nào? | Vùng I/II/III/IV; đối tượng áp dụng; không trả dưới mức tối thiểu |
| L05 | Thời gian báo trước khi đơn phương chấm dứt HĐLĐ xác định thời hạn là bao lâu? | Phân biệt NLĐ vs NSDLĐ; số ngày báo trước theo loại HĐLĐ |

#### 2.3. Câu hỏi tình huống pháp luật
Đơn phương chấm dứt HĐLĐ (NLĐ)
```bash
graphrag query "Chị Lan làm việc 2 năm, bị trả lương chậm 2 tháng liên tiếp. Chị có được đơn phương chấm dứt hợp đồng lao động ngay không? Cần báo trước bao lâu?" \
  --root data/labor-law --method local
```
Sa thải vs đơn phương chấm dứt (NSDLĐ)
```bash
graphrag query "Nhân viên vi phạm nội quy lần thứ 3, đã bị khiển trách và cảnh cáo. Công ty có được sa thải không? Cần thủ tục gì?" \
  --root data/labor-law --method local
```
Làm thêm giờ và trả lương
```bash
graphrag query "Công ty bắt làm thêm 4 giờ mỗi ngày trong 1 tháng và chỉ trả 100% lương giờ thường. Việc này có vi phạm pháp luật không? Mức trả lương làm thêm đúng ra sao?" \
  --root data/labor-law --method local
```
Thai sản và chấm dứt HĐLĐ
```bash
graphrag query "Người lao động nữ đang mang thai tháng thứ 7 bị công ty đơn phương chấm dứt hợp đồng vì lý do tái cơ cấu. Hành vi này có hợp pháp không?" \
  --root data/labor-law --method local
```
Tai nạn lao động và trách nhiệm
```bash
graphrag query "Người lao động bị tai nạn lao động do không sử dụng trang bị bảo hộ mà công ty đã cấp. Ai chịu trách nhiệm? Có được hưởng chế độ tai nạn lao động không?" \
  --root data/labor-law --method global
```
Thử việc và chấm dứt
```bash
graphrag query "Trong thời gian thử việc 60 ngày, ngày thứ 45 công ty thông báo không tiếp nhận vì không đạt yêu cầu nhưng không nêu lý do cụ thể. Công ty có vi phạm không?" \
  --root data/labor-law --method local
```
Tranh chấp đa bước (multi-hop)
```bash
graphrag query "Người lao động xin nghỉ không lương 6 tháng, sau đó quay lại làm việc nhưng công ty từ chối vì cho rằng đã coi như nghỉ việc. Quyền của người lao động và thủ tục nghỉ không lương theo luật ra sao?" \
  --root data/labor-law --method global
```
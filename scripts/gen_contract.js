const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign
  } = require('docx');
  const fs = require('fs');
  
  const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
  
  // Helper: mixed text with bold labels and normal values
  function infoLine(label, value, indent = 360) {
    return new Paragraph({
      children: [
        new TextRun({ text: label + " ", bold: true, size: 24, font: "Times New Roman" }),
        new TextRun({ text: value, size: 24, font: "Times New Roman" }),
      ],
      indent: { left: indent },
      spacing: { before: 60, after: 60 },
    });
  }
  
  function sectionTitle(text) {
    return new Paragraph({
      children: [new TextRun({ text, bold: true, size: 24, font: "Times New Roman", allCaps: true })],
      spacing: { before: 220, after: 80 },
    });
  }
  
  function articleTitle(text) {
    return new Paragraph({
      children: [new TextRun({ text, bold: true, size: 24, font: "Times New Roman" })],
      spacing: { before: 180, after: 60 },
    });
  }
  
  function para(text, leftIndent = 720) {
    return new Paragraph({
      children: [new TextRun({ text, size: 24, font: "Times New Roman" })],
      indent: leftIndent ? { left: leftIndent } : undefined,
      spacing: { before: 60, after: 60 },
    });
  }
  
  // Para with VIOLATION highlight (red underline comment)
  function paraViolation(normalText, violationText, note) {
    return new Paragraph({
      children: [
        new TextRun({ text: normalText, size: 24, font: "Times New Roman" }),
        new TextRun({ text: violationText, size: 24, font: "Times New Roman", color: "CC0000", bold: true, underline: {} }),
        new TextRun({ text: note ? "  [Vi phạm: " + note + "]" : "", size: 20, font: "Times New Roman", color: "CC0000", italics: true }),
      ],
      indent: { left: 720 },
      spacing: { before: 60, after: 60 },
    });
  }
  
  function bullet(text, violation = false, note = "") {
    return new Paragraph({
      children: [
        new TextRun({ text: "- " + text, size: 24, font: "Times New Roman", color: violation ? "CC0000" : "000000", bold: violation, underline: violation ? {} : undefined }),
        new TextRun({ text: note ? "  [Vi phạm: " + note + "]" : "", size: 20, font: "Times New Roman", color: "CC0000", italics: true }),
      ],
      indent: { left: 1080 },
      spacing: { before: 60, after: 60 },
    });
  }
  
  function emptyLine() {
    return new Paragraph({ children: [new TextRun({ text: "", size: 24 })], spacing: { before: 80, after: 80 } });
  }
  
  function violationBox(text) {
    const border = { style: BorderStyle.SINGLE, size: 4, color: "CC0000" };
    return new Table({
      width: { size: 9026, type: WidthType.DXA },
      columnWidths: [9026],
      rows: [
        new TableRow({
          children: [
            new TableCell({
              borders: { top: border, bottom: border, left: border, right: border },
              shading: { fill: "FFF0F0", type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 160, right: 160 },
              width: { size: 9026, type: WidthType.DXA },
              children: [
                new Paragraph({
                  children: [
                    new TextRun({ text: "⚠ GHI CHÚ VI PHẠM: ", bold: true, size: 22, font: "Times New Roman", color: "CC0000" }),
                    new TextRun({ text, size: 22, font: "Times New Roman", color: "CC0000", italics: true }),
                  ],
                  spacing: { before: 40, after: 40 },
                }),
              ]
            })
          ]
        })
      ]
    });
  }
  
  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Times New Roman", size: 24 } } }
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1134, right: 1134, bottom: 1134, left: 1701 },
        }
      },
      children: [
        // Header
        new Paragraph({
          children: [new TextRun({ text: "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", bold: true, size: 26, font: "Times New Roman" })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 60 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "Độc lập - Tự do - Hạnh phúc", bold: true, size: 24, font: "Times New Roman" })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 60 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "───────────────", size: 24, font: "Times New Roman" })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 160 },
        }),
  
        // Title
        new Paragraph({
          children: [new TextRun({ text: "HỢP ĐỒNG LAO ĐỘNG", bold: true, size: 32, font: "Times New Roman" })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 80 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "Số: 2024/HĐLĐ-TTS", size: 24, font: "Times New Roman" })],
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 200 },
        }),
  
        // Legal basis
        new Paragraph({ children: [new TextRun({ text: "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;", size: 24, font: "Times New Roman" })], spacing: { before: 60, after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: "Căn cứ Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm 2020 của Chính phủ;", size: 24, font: "Times New Roman" })], spacing: { before: 60, after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: "Căn cứ nhu cầu và khả năng của hai bên;", size: 24, font: "Times New Roman" })], spacing: { before: 60, after: 120 } }),
  
        new Paragraph({
          children: [new TextRun({ text: "Hôm nay, ngày 01 tháng 03 năm 2024, tại Công ty TNHH Tiến Thịnh Sơn, 45 Nguyễn Trãi, Quận Thanh Xuân, Hà Nội.", size: 24, font: "Times New Roman" })],
          spacing: { before: 60, after: 120 },
        }),
  
        // Party A
        sectionTitle("Bên A: Người sử dụng lao động"),
        infoLine("Tên doanh nghiệp:", "Công ty TNHH Tiến Thịnh Sơn"),
        infoLine("Địa chỉ:", "45 Nguyễn Trãi, Phường Thượng Đình, Quận Thanh Xuân, Hà Nội"),
        infoLine("Điện thoại:", "024 3859 1122"),
        infoLine("Mã số thuế:", "0109876543"),
        infoLine("Người đại diện theo pháp luật:", "Ông Trần Văn Đức"),
        infoLine("Chức vụ:", "Giám đốc"),
        emptyLine(),
  
        // Party B
        sectionTitle("Bên B: Người lao động"),
        infoLine("Họ và tên:", "Nguyễn Thị Lan Anh"),
        infoLine("Ngày tháng năm sinh:", "15/07/1998"),
        infoLine("Giới tính:", "Nữ"),
        infoLine("Số CCCD:", "001098765432"),
        infoLine("Ngày cấp:", "20/09/2021"),
        infoLine("Nơi cấp:", "Cục Cảnh sát quản lý hành chính về TTXH - Hà Nội"),
        infoLine("Địa chỉ thường trú:", "18 Ngõ 5, Đường Láng, Đống Đa, Hà Nội"),
        infoLine("Số điện thoại:", "0912 345 678"),
        emptyLine(),
  
        new Paragraph({
          children: [new TextRun({ text: "Hai bên cùng thỏa thuận ký kết Hợp đồng lao động với các điều khoản sau:", size: 24, font: "Times New Roman", bold: true })],
          spacing: { before: 100, after: 120 },
        }),
  
        // Article 1
        articleTitle("Điều 1. Loại hợp đồng và thời hạn hợp đồng"),
        para("1.1. Loại hợp đồng: Hợp đồng lao động xác định thời hạn."),
        para("1.2. Thời hạn hợp đồng: từ ngày 01 tháng 03 năm 2024 đến ngày 28 tháng 02 năm 2026 (24 tháng)."),
        para("1.3. Thời gian thử việc: 03 tháng, tính từ ngày 01 tháng 03 năm 2024."),
        emptyLine(),
        violationBox("Điều 1.3 vi phạm Điều 25 BLLĐ 2019: Thời gian thử việc tối đa đối với công việc có chức danh nghề nghiệp cần trình độ chuyên môn kỹ thuật trung cấp là 60 ngày (~2 tháng). Chức danh Nhân viên Kế toán chỉ được thử việc tối đa 60 ngày, không phải 03 tháng."),
        emptyLine(),
  
        // Article 2
        articleTitle("Điều 2. Công việc và địa điểm làm việc"),
        para("2.1. Vị trí công việc: Nhân viên Kế toán Tổng hợp."),
        para("2.2. Chức danh nghề nghiệp: Kế toán viên."),
        para("2.3. Địa điểm làm việc: Tầng 3, 45 Nguyễn Trãi, Quận Thanh Xuân, Hà Nội."),
        para("2.4. Mô tả công việc: Thực hiện hạch toán kế toán tổng hợp, lập báo cáo tài chính theo tháng/quý/năm, khai báo thuế, và các nhiệm vụ khác theo phân công."),
  
        // Article 3
        articleTitle("Điều 3. Tiền lương và chế độ đãi ngộ"),
        para("3.1. Mức lương cơ bản: 8.000.000 đồng/tháng (Tám triệu đồng chẵn/tháng)."),
        para("3.2. Phụ cấp: 500.000 đồng/tháng, bao gồm:"),
        bullet("Phụ cấp đi lại: 300.000 đồng/tháng"),
        bullet("Phụ cấp ăn trưa: 200.000 đồng/tháng"),
        para("3.3. Hình thức trả lương: Chuyển khoản ngân hàng."),
        paraViolation(
          "3.4. Kỳ trả lương: Vào ngày ",
          "mùng 10 của tháng tiếp theo",
          "Điều 97 BLLĐ 2019 quy định trả lương theo kỳ hạn không quá 1 tháng; thông lệ hợp lý là ngày cuối tháng hoặc đầu tháng kế. Trả vào ngày 10 tháng sau có thể gây chậm lương quá mức nếu tháng làm việc kết thúc ngày 28-31."
        ),
        emptyLine(),
        violationBox("Điều 3.1: Mức lương 8.000.000 đồng/tháng thấp hơn mức lương tối thiểu vùng I năm 2024 (4.960.000 đ/tháng theo NĐ 74/2024/NĐ-CP) — hợp lệ về mức sàn. Tuy nhiên lưu ý: mức lương thử việc theo Điều 26 BLLĐ không được thấp hơn 85% lương chính thức; nếu lương thử việc bị khấu trừ xuống dưới 6.800.000 đ/tháng sẽ vi phạm."),
        emptyLine(),
  
        // Article 4
        articleTitle("Điều 4. Thời giờ làm việc và nghỉ ngơi"),
        paraViolation(
          "4.1. Thời gian làm việc: ",
          "10 giờ/ngày, 6 ngày/tuần (60 giờ/tuần).",
          "Điều 105 BLLĐ 2019 quy định giờ làm việc bình thường không quá 8 giờ/ngày và 48 giờ/tuần. Vi phạm nghiêm trọng."
        ),
        emptyLine(),
        violationBox("Điều 4.1 vi phạm Điều 105 BLLĐ 2019: Giờ làm việc bình thường không quá 8 giờ/ngày, không quá 48 giờ/tuần. Quy định 10 giờ/ngày và 60 giờ/tuần vượt quá giới hạn pháp luật cho phép, đồng thời phần vượt quá (2 giờ/ngày) phải được tính là giờ làm thêm và được trả lương làm thêm giờ theo Điều 107."),
        emptyLine(),
        para("4.2. Giờ làm việc cụ thể: Từ 7h30 đến 12h00 (buổi sáng); từ 13h00 đến 18h30 (buổi chiều)."),
        para("4.3. Nghỉ hàng tuần: Nghỉ Chủ nhật hàng tuần."),
        paraViolation(
          "4.4. Nghỉ phép năm: Người lao động được hưởng ",
          "08 ngày phép/năm",
          "Điều 113 BLLĐ 2019 quy định tối thiểu 12 ngày phép/năm với người làm việc đủ 12 tháng. Quy định 08 ngày là vi phạm quyền nghỉ phép của người lao động."
        ),
        emptyLine(),
        violationBox("Điều 4.4 vi phạm Điều 113 BLLĐ 2019: Người lao động làm việc đủ 12 tháng được nghỉ hằng năm hưởng nguyên lương ít nhất 12 ngày làm việc. Hợp đồng ghi 08 ngày thấp hơn mức tối thiểu pháp luật, điều khoản này vô hiệu và phải áp dụng quy định của pháp luật."),
        emptyLine(),
        para("4.5. Nghỉ lễ, Tết: Theo quy định của pháp luật hiện hành."),
  
        // Article 5
        articleTitle("Điều 5. Bảo hiểm xã hội, bảo hiểm y tế và bảo hiểm thất nghiệp"),
        para("5.1. Bên A có trách nhiệm tham gia bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp cho Bên B theo quy định của pháp luật hiện hành."),
        paraViolation(
          "5.2. Tuy nhiên, trong ",
          "06 tháng đầu thử việc, Bên A không đóng bảo hiểm xã hội cho Bên B",
          "Điều 2 Luật BHXH 2014 quy định người lao động có HĐLĐ từ 03 tháng trở lên phải tham gia BHXH bắt buộc. Không đóng BHXH trong thời gian thử việc là vi phạm pháp luật."
        ),
        emptyLine(),
        violationBox("Điều 5.2 vi phạm Điều 2 Luật BHXH 2014 và Điều 168 BLLĐ 2019: Người sử dụng lao động bắt buộc phải tham gia BHXH, BHYT, BHTN ngay từ khi ký hợp đồng lao động từ 03 tháng trở lên, kể cả trong thời gian thử việc. Không thể miễn trừ nghĩa vụ này bằng thỏa thuận trong hợp đồng."),
        emptyLine(),
  
        // Article 6
        articleTitle("Điều 6. Quyền và nghĩa vụ của Bên B (Người lao động)"),
        para("6.1. Quyền lợi của Người lao động:", false),
        bullet("Được hưởng lương, thưởng và các khoản phúc lợi theo thỏa thuận;"),
        bullet("Được tham gia đào tạo, nâng cao kỹ năng nghề nghiệp;"),
        bullet("Được hưởng các chế độ BHXH, BHYT, BHTN theo quy định;"),
        bullet("Được nghỉ lễ, Tết theo quy định pháp luật;"),
        para("6.2. Nghĩa vụ của Người lao động:", false),
        bullet("Thực hiện đúng và đầy đủ các công việc được giao;"),
        bullet("Chấp hành nội quy lao động và quy chế Công ty;"),
        bullet("Bảo vệ tài sản, bí mật kinh doanh của Công ty;"),
        paraViolation(
          "- ",
          "Không được mang thai hoặc sinh con trong thời hạn hợp đồng; nếu vi phạm Công ty có quyền chấm dứt hợp đồng.",
          "Vi phạm nghiêm trọng Điều 137 BLLĐ 2019 — cấm sa thải/đơn phương chấm dứt HĐLĐ với lao động nữ mang thai, sinh con, nuôi con dưới 12 tháng tuổi."
        ),
        emptyLine(),
        violationBox("Điều 6.2 vi phạm Điều 137 BLLĐ 2019: Nghiêm cấm người sử dụng lao động sa thải hoặc đơn phương chấm dứt hợp đồng với người lao động vì lý do kết hôn, mang thai, nghỉ thai sản hoặc nuôi con dưới 12 tháng tuổi. Điều khoản này hoàn toàn vô hiệu về mặt pháp lý."),
        emptyLine(),
  
        // Article 7
        articleTitle("Điều 7. Quyền và nghĩa vụ của Bên A (Người sử dụng lao động)"),
        para("7.1. Bên A có quyền điều hành, phân công công việc cho Bên B theo phạm vi hợp đồng."),
        para("7.2. Bên A có nghĩa vụ thanh toán đầy đủ, đúng hạn tiền lương và các chế độ phúc lợi khác."),
        para("7.3. Bên A bảo đảm điều kiện làm việc an toàn, vệ sinh cho Người lao động."),
        paraViolation(
          "7.4. Bên A có quyền ",
          "khấu trừ lương tháng của Bên B để bù đắp chi phí đào tạo nội bộ theo quyết định của Giám đốc, tối đa không giới hạn.",
          "Điều 102 BLLĐ 2019 giới hạn mức khấu trừ lương tối đa 30%/kỳ lương sau khi đóng BHXH và thuế TNCN."
        ),
        emptyLine(),
        violationBox("Điều 7.4 vi phạm Điều 102 BLLĐ 2019: Người sử dụng lao động chỉ được khấu trừ lương để bồi thường thiệt hại theo Điều 102, không vượt quá 30% tiền lương thực lĩnh hàng tháng. Điều khoản 'không giới hạn' theo quyết định đơn phương của Giám đốc là trái luật và vô hiệu."),
        emptyLine(),
  
        // Article 8
        articleTitle("Điều 8. Chấm dứt hợp đồng lao động"),
        para("8.1. Hợp đồng chấm dứt trong các trường hợp: hết thời hạn; hai bên thỏa thuận; người lao động đủ điều kiện hưởng lương hưu; các trường hợp khác theo pháp luật."),
        paraViolation(
          "8.2. Nếu Bên B đơn phương chấm dứt hợp đồng, Bên B phải ",
          "nộp phạt vi phạm bằng 03 tháng lương cho Bên A.",
          "Điều 35 BLLĐ 2019 không quy định người lao động phải nộp phạt khi đơn phương chấm dứt đúng luật. Người lao động chỉ phải bồi hoàn chi phí đào tạo theo Điều 62 (nếu có cam kết)."
        ),
        emptyLine(),
        violationBox("Điều 8.2 vi phạm Điều 35 và Điều 40 BLLĐ 2019: Người lao động đơn phương chấm dứt hợp đồng đúng luật (báo trước đúng thời hạn) không có nghĩa vụ nộp 'phạt vi phạm' cho người sử dụng lao động. Quy định phạt 03 tháng lương là trái pháp luật và không có hiệu lực thi hành."),
        emptyLine(),
        para("8.3. Khi chấm dứt hợp đồng, Bên A thanh toán đầy đủ các khoản tiền lương còn lại và quyền lợi khác trong 14 ngày làm việc."),
  
        // Article 9
        articleTitle("Điều 9. Giải quyết tranh chấp"),
        para("9.1. Tranh chấp được giải quyết trước hết bằng thương lượng, hòa giải."),
        para("9.2. Nếu không thỏa thuận được, tranh chấp đưa ra Hội đồng trọng tài lao động hoặc Tòa án nhân dân có thẩm quyền."),
  
        // Article 10
        articleTitle("Điều 10. Các điều khoản khác"),
        para("10.1. Hợp đồng lập thành 02 bản có giá trị pháp lý như nhau, mỗi bên giữ 01 bản."),
        para("10.2. Hợp đồng có hiệu lực từ ngày 01/03/2024."),
        para("10.3. Các vấn đề khác không đề cập trong hợp đồng thực hiện theo quy định của Bộ luật Lao động và các văn bản pháp luật liên quan."),
  
        emptyLine(),
        emptyLine(),
  
        // Summary violation box
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [9026],
          rows: [
            new TableRow({
              children: [
                new TableCell({
                  borders: { top: { style: BorderStyle.SINGLE, size: 8, color: "8B0000" }, bottom: { style: BorderStyle.SINGLE, size: 8, color: "8B0000" }, left: { style: BorderStyle.SINGLE, size: 8, color: "8B0000" }, right: { style: BorderStyle.SINGLE, size: 8, color: "8B0000" } },
                  shading: { fill: "FFE5E5", type: ShadingType.CLEAR },
                  margins: { top: 120, bottom: 120, left: 200, right: 200 },
                  width: { size: 9026, type: WidthType.DXA },
                  children: [
                    new Paragraph({ children: [new TextRun({ text: "TÓM TẮT CÁC VI PHẠM TRONG HỢP ĐỒNG NÀY", bold: true, size: 24, font: "Times New Roman", color: "8B0000" })], alignment: AlignmentType.CENTER, spacing: { before: 60, after: 100 } }),
                    new Paragraph({ children: [new TextRun({ text: "1. Điều 1.3 — Thử việc 03 tháng (vi phạm Điều 25 BLLĐ: tối đa 60 ngày với lao động chuyên môn kỹ thuật)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 60, after: 40 } }),
                    new Paragraph({ children: [new TextRun({ text: "2. Điều 4.1 — Làm 10 giờ/ngày, 60 giờ/tuần (vi phạm Điều 105 BLLĐ: tối đa 8 giờ/ngày, 48 giờ/tuần)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 40, after: 40 } }),
                    new Paragraph({ children: [new TextRun({ text: "3. Điều 4.4 — Nghỉ phép 08 ngày/năm (vi phạm Điều 113 BLLĐ: tối thiểu 12 ngày/năm)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 40, after: 40 } }),
                    new Paragraph({ children: [new TextRun({ text: "4. Điều 5.2 — Không đóng BHXH trong thời gian thử việc (vi phạm Điều 168 BLLĐ và Luật BHXH 2014)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 40, after: 40 } }),
                    new Paragraph({ children: [new TextRun({ text: "5. Điều 6.2 — Cấm mang thai/sinh con (vi phạm Điều 137 BLLĐ: cấm phân biệt đối xử với lao động nữ mang thai)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 40, after: 40 } }),
                    new Paragraph({ children: [new TextRun({ text: "6. Điều 7.4 — Khấu trừ lương không giới hạn (vi phạm Điều 102 BLLĐ: tối đa 30% lương thực lĩnh)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 40, after: 40 } }),
                    new Paragraph({ children: [new TextRun({ text: "7. Điều 8.2 — Phạt 03 tháng lương khi thôi việc (vi phạm Điều 35 & 40 BLLĐ: không có quy định phạt người lao động)", size: 22, font: "Times New Roman", color: "8B0000" })], indent: { left: 200 }, spacing: { before: 40, after: 80 } }),
                  ]
                })
              ]
            })
          ]
        }),
  
        emptyLine(),
        emptyLine(),
  
        // Signature
        new Table({
          width: { size: 9026, type: WidthType.DXA },
          columnWidths: [4513, 4513],
          rows: [
            new TableRow({
              children: [
                new TableCell({
                  borders: noBorders,
                  width: { size: 4513, type: WidthType.DXA },
                  children: [
                    new Paragraph({ children: [new TextRun({ text: "ĐẠI DIỆN BÊN A", bold: true, size: 24, font: "Times New Roman" })], alignment: AlignmentType.CENTER }),
                    new Paragraph({ children: [new TextRun({ text: "(Ký, ghi rõ họ tên, đóng dấu)", size: 22, font: "Times New Roman", italics: true })], alignment: AlignmentType.CENTER, spacing: { before: 40, after: 200 } }),
                  ]
                }),
                new TableCell({
                  borders: noBorders,
                  width: { size: 4513, type: WidthType.DXA },
                  children: [
                    new Paragraph({ children: [new TextRun({ text: "BÊN B", bold: true, size: 24, font: "Times New Roman" })], alignment: AlignmentType.CENTER }),
                    new Paragraph({ children: [new TextRun({ text: "(Ký, ghi rõ họ tên)", size: 22, font: "Times New Roman", italics: true })], alignment: AlignmentType.CENTER, spacing: { before: 40, after: 200 } }),
                  ]
                }),
              ]
            }),
            new TableRow({
              children: [
                new TableCell({
                  borders: noBorders,
                  width: { size: 4513, type: WidthType.DXA },
                  children: [
                    new Paragraph({ children: [new TextRun({ text: "", size: 24 })], spacing: { before: 700 } }),
                    new Paragraph({ children: [new TextRun({ text: "Trần Văn Đức", bold: true, size: 24, font: "Times New Roman" })], alignment: AlignmentType.CENTER }),
                  ]
                }),
                new TableCell({
                  borders: noBorders,
                  width: { size: 4513, type: WidthType.DXA },
                  children: [
                    new Paragraph({ children: [new TextRun({ text: "", size: 24 })], spacing: { before: 700 } }),
                    new Paragraph({ children: [new TextRun({ text: "Nguyễn Thị Lan Anh", bold: true, size: 24, font: "Times New Roman" })], alignment: AlignmentType.CENTER }),
                  ]
                }),
              ]
            }),
          ]
        }),
      ]
    }]
  });
  
  Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync("./data-contracts/hop_dong_lao_dong_vi_pham.docx", buffer);
    console.log("Done!");
  });
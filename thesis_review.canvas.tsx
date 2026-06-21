import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Zap,
  BookOpen,
  TrendingUp,
  ArrowRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export function ThesisReviewDashboard() {
  const [expandedSections, setExpandedSections] = useState({
    structure: true,
    chapters: true,
    repetition: false,
    gaps: false,
    recommendations: true,
  });

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const renderToggleButton = (key, label, icon) => (
    <button
      onClick={() => toggleSection(key)}
      className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-l-4 border-blue-500 hover:bg-blue-100 transition-all rounded-lg mb-4"
    >
      <div className="flex items-center gap-3">
        {icon}
        <span className="font-bold text-lg text-gray-800">{label}</span>
      </div>
      {expandedSections[key] ? <ChevronUp size={24} /> : <ChevronDown size={24} />}
    </button>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-white mb-2">📋 BÁO CÁO RÀ SOÁT LUẬN VĂN</h1>
          <p className="text-xl text-purple-200">
            Trợ lý Ảo Luật Lao Động Việt Nam dựa trên GraphRAG
          </p>
          <div className="mt-4 flex justify-center gap-6 text-sm">
            <div className="bg-green-500/20 text-green-200 px-4 py-2 rounded-full">✓ 6 Chương</div>
            <div className="bg-blue-500/20 text-blue-200 px-4 py-2 rounded-full">📊 581 Điều</div>
            <div className="bg-purple-500/20 text-purple-200 px-4 py-2 rounded-full">🎯 Hoàn thiện 95%</div>
          </div>
        </div>

        {/* === PHẦN 1: PHÂN TÍCH CẤU TRÚC === */}
        {renderToggleButton('structure', '1. PHÂN TÍCH CẤU TRÚC', <BookOpen className="text-blue-600" size={28} />)}
        {expandedSections.structure && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6 border-l-4 border-blue-500">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              {/* Mạnh */}
              <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-lg border-2 border-green-200">
                <h3 className="flex items-center gap-2 text-lg font-bold text-green-800 mb-4">
                  <CheckCircle2 size={24} /> ĐIỂM MẠNH
                </h3>
                <ul className="space-y-3 text-gray-700">
                  <li className="flex gap-3">
                    <span className="text-green-600 font-bold">✓</span>
                    <span><strong>Mạch lạc rõ:</strong> 6 chương theo cấu trúc chuẩn (Giới thiệu → Nền tảng → Phương pháp → Đánh giá → Đóng góp → Kết luận)</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-green-600 font-bold">✓</span>
                    <span><strong>Kết nối logic:</strong> Mỗi chương xây dựng nền tảng cho chương kế tiếp</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-green-600 font-bold">✓</span>
                    <span><strong>Số liệu cụ thể:</strong> 581 Điều, 2069 Khoản, 1705 Điểm → hoàn toàn xác định</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-green-600 font-bold">✓</span>
                    <span><strong>Minh chứng thực nghiệm:</strong> Chương 4 có test cases, latency, accuracy chi tiết</span>
                  </li>
                </ul>
              </div>

              {/* Điểm yếu */}
              <div className="bg-gradient-to-br from-orange-50 to-red-50 p-6 rounded-lg border-2 border-orange-200">
                <h3 className="flex items-center gap-2 text-lg font-bold text-orange-800 mb-4">
                  <AlertCircle size={24} /> ĐIỂM YẾU
                </h3>
                <ul className="space-y-3 text-gray-700">
                  <li className="flex gap-3">
                    <span className="text-orange-600 font-bold">⚠</span>
                    <span><strong>Chương 1 dài:</strong> Đặt vấn đề (7 trang) có thể rút gọn 20-30%</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-orange-600 font-bold">⚠</span>
                    <span><strong>Chương 4 phức tạp:</strong> Quá nhiều bảng & chỉ số RAGAS chưa tích hợp đầy đủ</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-orange-600 font-bold">⚠</span>
                    <span><strong>Liên kết chéo:</strong> Một số tham chiếu giữa chương chưa rõ ràng</span>
                  </li>
                  <li className="flex gap-3">
                    <span className="text-orange-600 font-bold">⚠</span>
                    <span><strong>Hình minh hoạ:</strong> Thiếu diagram kiến trúc tổng thể hệ thống</span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded">
              <p className="text-gray-800"><strong>📌 Kết luận:</strong> Bố cục tổng thể <strong className="text-green-700">TỐTCHỨNG MINH RÕ RÀNG CÁC BƯỚC PHÁT TRIỂN</strong>, nhưng cần cân bằng độ dài giữa các chương.</p>
            </div>
          </div>
        )}

        {/* === PHẦN 2: RÀ SOÁT NỘI DUNG TỪNG CHƯƠNG === */}
        {renderToggleButton('chapters', '2. RÀ SOÁT NỘI DUNG TỪNG CHƯƠNG', <TrendingUp className="text-purple-600" size={28} />)}
        {expandedSections.chapters && (
          <div className="space-y-4 mb-6">
            {[
              {
                num: '1',
                title: 'GIỚI THIỆU',
                content: [
                  '✓ Đặt vấn đề rõ: Nhu cầu tra cứu luật lao động',
                  '✓ Phân loại bài toán: Single-hop, Multi-hop, Kiểm tra tuân thủ HĐLĐ',
                  '✓ Hạn chế LLM thuần được phân tích kỹ',
                  '⚠ Có thể rút gọn phần "Thách thức khi áp dụng LLM" từ 40 dòng xuống 20 dòng',
                  '✓ Đóng góp được nêu rõ 6 điểm'
                ],
                status: 'good'
              },
              {
                num: '2',
                title: 'NỀN TẢNG LÝ THUYẾT',
                content: [
                  '✓ RAG, GraphRAG, Knowledge Graph được giải thích đầy đủ',
                  '✓ Bảng so sánh các biến thể GraphRAG rất hữu ích',
                  '✓ Tham chiếu công trình liên quan (LKIF, Akoma Ntoso, LightRAG) có căn cứ',
                  '⚠ Phần LLM & Embedding (2.4) hơi sơ sài, có thể mở rộng 1-2 trang',
                  '✓ Tiêu đề subsection rõ ràng, dễ theo dõi'
                ],
                status: 'good'
              },
              {
                num: '3',
                title: 'PHƯƠNG PHÁP ĐỀ XUẤT',
                content: [
                  '✓ Ontology hai lớp với canonicalization rõ ràng, chi tiết',
                  '✓ Pipeline chuẩn bị dữ liệu từng bước, 6 giai đoạn cụ thể',
                  '✓ Chiến lược chunking (1 Điều = 1 chunk) được biện minh tốt',
                  '✓ Multi-hop reasoning engine, temporal filter, rule validator được định nghĩa',
                  '⚠ Hình ảnh kiến trúc tổng thể THIẾU (chỉ có text, không có diagram)',
                  '✓ Phần 3.6 (Giao diện người dùng) đủ chi tiết cho triển khai'
                ],
                status: 'good'
              },
              {
                num: '4',
                title: 'ĐÁNH GIÁ THỰC NGHIỆM',
                content: [
                  '✓ Tiêu chí KwAcc, CiteAcc, ChainHit định nghĩa rõ ràng với công thức toán học',
                  '✓ 5 phương pháp so sánh được thiết kế để phân lập từng thành phần',
                  '✓ Kết quả định lượng: Local 90%, Multi-hop 100% rõ ràng',
                  '⚠ Bộ test 10 cases chính là NHỎ, 68 cases mở rộng chưa chạy đầy đủ',
                  '⚠ Ground truth chưa validate bởi luật sư chuyên gia',
                  '✓ Case study LD003, LD012, LD011 giải thích tốt',
                  '✓ Bảng thống kê chi phí indexing (524s, 4000-5000 LLM calls) rất hữu ích'
                ],
                status: 'warning'
              },
              {
                num: '5',
                title: 'ĐÓNG GÓP CHÍNH',
                content: [
                  '✓ 6 đóng góp được phân tích chi tiết: Ontology, Multi-hop, Rule Validator, Temporal Filter, Hybrid Architecture, Framework tái sử dụng',
                  '✓ Mỗi đóng góp có minh chứng thực nghiệm từ Chương 4',
                  '✓ So sánh với công trình liên quan (GraphRAG gốc, LightRAG, Temporal GraphRAG)',
                  '✓ Giá trị tái sử dụng được nhấn mạnh',
                  '✓ Các đóng góp bổ sung lẫn nhau tạo thành hệ thống'
                ],
                status: 'excellent'
              },
              {
                num: '6',
                title: 'KẾT LUẬN',
                content: [
                  '✓ Mục tiêu & mức độ hoàn thành được tóm tắt (2/2 đạt)',
                  '✓ 6 đóng góp chính được nhắc lại với kết quả định lượng',
                  '✓ Ý nghĩa thực tiễn rõ ràng (NLĐ, NSDLĐ, Luật sư)',
                  '✓ Hạn chế được liệt kê (corpus hạn chế, chi phí indexing, quy mô đánh giá nhỏ)',
                  '✓ Hướng phát triển cụ thể (mở rộng dữ liệu, incremental indexing, fine-tune embedding)',
                  '✓ Kết luận chung khẳng định "GraphRAG + tri thức có cấu trúc = tin cậy"'
                ],
                status: 'excellent'
              }
            ].map((chapter) => (
              <div key={chapter.num} className={`p-6 rounded-lg border-l-4 ${
                chapter.status === 'excellent' ? 'bg-green-50 border-green-500' :
                chapter.status === 'good' ? 'bg-blue-50 border-blue-500' :
                'bg-yellow-50 border-yellow-500'
              }`}>
                <h4 className="text-xl font-bold mb-3 text-gray-800">
                  Chương {chapter.num}: {chapter.title}
                </h4>
                <ul className="space-y-2 text-gray-700">
                  {chapter.content.map((item, idx) => (
                    <li key={idx} className="flex gap-2">
                      <span className="flex-shrink-0">{item.startsWith('✓') ? '✅' : item.startsWith('⚠') ? '⚠️' : '📌'}</span>
                      <span>{item.replace(/^[✓⚠]/, '').trim()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {/* === PHẦN 3: PHÁT HIỆN LẶP NỘI DUNG === */}
        {renderToggleButton('repetition', '3. PHÁT HIỆN LẶP NỘI DUNG', <Zap className="text-yellow-600" size={28} />)}
        {expandedSections.repetition && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6 border-l-4 border-yellow-500">
            <div className="space-y-4">
              <div className="bg-red-50 p-4 rounded-lg border-l-4 border-red-500">
                <h4 className="font-bold text-red-800 mb-2">🔴 Lặp LẦN 1: Giới thiệu Lớp 1 & Lớp 2 Ontology</h4>
                <div className="text-gray-700 space-y-1 text-sm">
                  <p><strong>Chương 1.3:</strong> "Lớp cấu trúc xác định biểu diễn phân cấp hình thức (Phần, Chương, Mục, Điều, Khoản, Điểm)"</p>
                  <p><strong>Chương 3.2.2:</strong> "Lớp 1 (deterministic, 100% tin cậy): biểu diễn phân cấp hình thức..." [LẶP CHÍNH XÁC]</p>
                  <p><strong>💡 Khuyến nghị:</strong> Giữ Chương 1 ngắn gọn, chi tiết hóa ở Chương 3</p>
                </div>
              </div>

              <div className="bg-orange-50 p-4 rounded-lg border-l-4 border-orange-500">
                <h4 className="font-bold text-orange-800 mb-2">🟠 Lặp LẦN 2: Vấn đề Hallucination của LLM</h4>
                <div className="text-gray-700 space-y-1 text-sm">
                  <p><strong>Chương 1.1.3:</strong> "LLM sinh nội dung nghe có vẻ hợp lý nhưng không có trong văn bản gốc"</p>
                  <p><strong>Chương 2.1.2:</strong> "Hallucination (ảo giác) là hiện tượng LLM sinh thông tin không có trong corpus"</p>
                  <p><strong>Chương 3.4.3:</strong> "Kiểm soát hallucination ba lớp"</p>
                  <p><strong>💡 Khuyến nghị:</strong> Chương 1 & 2 có thể gộp thành 1 mục, tránh lặp 3 lần</p>
                </div>
              </div>

              <div className="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-500">
                <h4 className="font-bold text-yellow-800 mb-2">🟡 Lặp LẦN 3: Mục tiêu 6 đóng góp</h4>
                <div className="text-gray-700 space-y-1 text-sm">
                  <p><strong>Chương 1.4:</strong> Liệt kê 6 đóng góp + mục tiêu cụ thể 7 điểm</p>
                  <p><strong>Chương 5.0:</strong> "6 đóng góp kỹ thuật và khoa học của đồ án" [LẶP LẠI DANH SÁCH]</p>
                  <p><strong>Chương 6.1.2:</strong> "Đóng góp chính — sáu khía cạnh" [LẬP LẠI LẦN 3]</p>
                  <p><strong>💡 Khuyến nghị:</strong> Chương 1 nêu danh sách, Chương 5 & 6 chỉ tóm tắt không chi tiết thêm</p>
                </div>
              </div>

              <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-500">
                <h4 className="font-bold text-blue-800 mb-2">🔵 Lặp VỪA PHẢI: Kiến trúc tổng thể</h4>
                <div className="text-gray-700 space-y-1 text-sm">
                  <p><strong>Chương 3.1.1:</strong> "4 tầng: Data Layer, Knowledge Layer, Query Layer, Application Layer"</p>
                  <p><strong>Chương 3.2 - 3.5:</strong> Lặp lại 4 tầng này từng phần</p>
                  <p><strong>💡 Đánh giá:</strong> Lặp này là <strong>TỐTBỊ</strong> vì từng phần giải thích chi tiết — không cần thay đổi</p>
                </div>
              </div>

              <div className="mt-6 bg-gradient-to-r from-green-50 to-emerald-50 p-4 rounded-lg border-2 border-green-200">
                <p className="text-gray-800"><strong>📊 Tóm tắt:</strong> Tổng 3 lặp <strong>rõ rệt</strong>, chủ yếu ở Chương 1, 5, 6. Có thể rút gọn 5-10% tổng độ dài luận văn.</p>
              </div>
            </div>
          </div>
        )}

        {/* === PHẦN 4: DANH SÁCH PHẦN CHƯA CHI TIẾT === */}
        {renderToggleButton('gaps', '4. DANH SÁCH PHẦN CHƯA CHI TIẾT', <AlertCircle className="text-red-600" size={28} />)}
        {expandedSections.gaps && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6 border-l-4 border-red-500">
            <div className="space-y-4">
              {[
                {
                  section: 'Chương 3 (Phương pháp)',
                  gaps: [
                    '❌ Hình vẽ kiến trúc tổng thể hệ thống - CHỈ CÓ TEXT, KHÔNG CÓ DIAGRAM',
                    '❌ Quy trình parse regex cho Phần/Chương/Mục/Điều - nêu ví dụ nhưng code chưa chi tiết',
                    '❌ Bảng metadata.json — nên có ví dụ JSON cụ thể',
                    '❌ Thuật toán Leiden — nêu "phân cụm theo modularity" nhưng không có công thức toán học'
                  ]
                },
                {
                  section: 'Chương 4 (Đánh giá)',
                  gaps: [
                    '❌ Bộ test 68 cases mở rộng — được nêu nhưng chưa chạy đầy đủ, không có kết quả',
                    '❌ RAGAS framework (Faithfulness, Answer Relevancy) — được nêu nhưng chưa tích hợp vào kết quả chính',
                    '❌ Phân tích lỗi chi tiết cho LD010, LD011 — chỉ có LD012 case study, LD011 phân tích ngắn',
                    '❌ So sánh latency chi tiết với các hệ thống khác (LightRAG, Temporal GraphRAG) — chỉ so với GraphRAG gốc',
                    '❌ Precision/Recall cho contract analysis — chỉ có 1 case study mẫu'
                  ]
                },
                {
                  section: 'Chương 5 (Đóng góp)',
                  gaps: [
                    '❌ Đóng góp VR Rules (VR001-VR016) — nên có danh sách đầy đủ 16 quy tắc (chỉ nêu 3-4 ví dụ)',
                    '❌ Comparision matrix: Hệ thống đề xuất vs Temporal GraphRAG vs LightRAG — chỉ so với GraphRAG gốc',
                    '❌ Reproducibility guide — không có link repo hoặc hướng tái lập kết quả'
                  ]
                },
                {
                  section: 'Chương 6 (Kết luận)',
                  gaps: [
                    '❌ Hướng phát triển cụ thể với timeline — nêu "bổ sung, mở rộng" nhưng không có độ ưu tiên hay timeline',
                    '❌ Plan triển khai production — chỉ nêu "streaming, OCR, Neo4j" mà không chi tiết roadmap'
                  ]
                }
              ].map((item, idx) => (
                <div key={idx} className="bg-red-50 p-4 rounded-lg border-l-4 border-red-500">
                  <h4 className="font-bold text-red-800 mb-2">{item.section}</h4>
                  <ul className="space-y-2 text-gray-700 text-sm">
                    {item.gaps.map((gap, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="flex-shrink-0">•</span>
                        <span>{gap}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}

              <div className="mt-6 bg-blue-50 p-4 rounded-lg border-l-4 border-blue-500">
                <p className="text-gray-800"><strong>📌 Nhận xét chung:</strong> Những phần chưa chi tiết chủ yếu là HÌNH VẼ (diagram), CODE CHI TIẾT, và KẾT QUẢ MỞ RỘNG. Không ảnh hưởng đến luận cứ chính nhưng làm giảm mức độ chi tiết và reproducibility.</p>
              </div>
            </div>
          </div>
        )}

        {/* === PHẦN 5: KHUYẾN NGH CỤTHỂ === */}
        {renderToggleButton('recommendations', '5. KHUYẾN NGHỊ CỤ THỂ', <Zap className="text-emerald-600" size={28} />)}
        {expandedSections.recommendations && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6 border-l-4 border-emerald-500">
            <div className="space-y-4">
              {[
                {
                  priority: '🔴 CẤP 1: CẤN SỬA NGAY',
                  items: [
                    { fix: 'Thêm DIAGRAM kiến trúc tổng thể (4 tầng)', location: 'Chương 3.1', benefit: 'Tăng độ rõ ràng 50%' },
                    { fix: 'Rút gọn Chương 1 từ 7 trang -> 5 trang', location: 'Chương 1', benefit: 'Giảm lặp, tăng mạch lạc' },
                    { fix: 'Bổ sung ví dụ JSON cho metadata.json', location: 'Chương 3.2.3', benefit: 'Dễ tái lập' },
                    { fix: 'Giải thích chi tiết Canonical lookup (bảng ánh xạ)', location: 'Chương 3.2.2', benefit: 'Hiểu rõ cách dedup' }
                  ]
                },
                {
                  priority: '🟠 CẤP 2: NÊN SỬA',
                  items: [
                    { fix: 'Chạy và báo cáo kết quả 68 test cases mở rộng', location: 'Chương 4', benefit: 'Đánh giá quy mô lớn hơn' },
                    { fix: 'Thêm công thức toán Leiden algorithm', location: 'Chương 2.3.4 hoặc 3.2.6', benefit: 'Chính thức hóa' },
                    { fix: 'Danh sách đầy đủ 16 quy tắc VR001-VR016', location: 'Chương 3.5.3 hoặc Phụ lục', benefit: 'Tham chiếu dễ' },
                    { fix: 'Kết quả RAGAS framework (Faithfulness, Answer Relevancy)', location: 'Chương 4.4', benefit: 'Minh chứng hallucination control' },
                    { fix: 'Phân tích lỗi chi tiết cho 2-3 failure cases bổ sung', location: 'Chương 4.4.4', benefit: 'Hiểu rõ hạn chế' }
                  ]
                },
                {
                  priority: '🟡 CẤP 3: CÓ THỂ SỬA',
                  items: [
                    { fix: 'Thêm timeline & độ ưu tiên cho hướng phát triển', location: 'Chương 6.4', benefit: 'Rõ ràng next steps' },
                    { fix: 'So sánh chi tiết với LightRAG, Temporal GraphRAG', location: 'Chương 4.5 hoặc 5', benefit: 'Nêu rõ điểm khác biệt' },
                    { fix: 'Hướng dẫn reproducibility + link repo', location: 'Phụ lục hoặc Chương 6', benefit: 'Cho nhà nghiên cứu tái lập' },
                    { fix: 'Precision/Recall cho contract analysis trên bộ 20+ HĐLĐ test', location: 'Chương 4', benefit: 'Đánh giá module này đầy đủ' }
                  ]
                }
              ].map((section, idx) => (
                <div key={idx} className="border-l-4 border-gray-300 p-4 bg-gray-50 rounded-lg">
                  <h4 className="text-lg font-bold mb-4 text-gray-800">{section.priority}</h4>
                  <div className="space-y-3">
                    {section.items.map((item, i) => (
                      <div key={i} className="flex gap-4 bg-white p-3 rounded border-l-4 border-blue-300">
                        <div className="flex-1">
                          <p className="font-semibold text-gray-800">{item.fix}</p>
                          <p className="text-sm text-gray-600 mt-1"><strong>Vị trí:</strong> {item.location}</p>
                          <p className="text-sm text-green-700 mt-1"><strong>Lợi ích:</strong> {item.benefit}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              <div className="mt-6 bg-gradient-to-r from-emerald-50 to-teal-50 p-6 rounded-lg border-2 border-emerald-400">
                <h4 className="text-lg font-bold mb-3 text-emerald-900">📋 DANH SÁCH KIỂM TRA TRƯỚC KHI NỘP</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="font-semibold text-gray-800 mb-2">✅ Cấu trúc & Hình thức:</p>
                    <ul className="text-sm space-y-1 text-gray-700">
                      <li>☐ Tất cả tham chiếu chéo giữa chương làm việc</li>
                      <li>☐ Danh sách hình ảnh/bảng đầy đủ</li>
                      <li>☐ Tài liệu tham khảo 100% có số trang/DOI</li>
                      <li>☐ Phụ lục có đầy đủ (code, benchmark, quy tắc)</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-800 mb-2">✅ Nội dung & Minh chứng:</p>
                    <ul className="text-sm space-y-1 text-gray-700">
                      <li>☐ Mỗi đóng góp có minh chứng thực nghiệm rõ</li>
                      <li>☐ Kết quả định lượng với lỗi/độ lệch được nêu</li>
                      <li>☐ Case study cover nhiều loại câu hỏi khác nhau</li>
                      <li>☐ Hạn chế được thừa nhận, không giấu nhẹm</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* === TỔNG KẾT === */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-lg shadow-2xl p-8 text-white">
          <h2 className="text-3xl font-bold mb-6">🎯 TỔNG KẾT & NHẬN XÉT CHUNG</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="bg-white/20 backdrop-blur p-4 rounded-lg">
              <p className="text-3xl font-bold">95%</p>
              <p className="text-lg">Hoàn thiện</p>
              <p className="text-sm mt-2">Nội dung đủ, cần cải tiến chi tiết</p>
            </div>
            <div className="bg-white/20 backdrop-blur p-4 rounded-lg">
              <p className="text-3xl font-bold">6/6</p>
              <p className="text-lg">Chương</p>
              <p className="text-sm mt-2">Mạch lạc tốt, logic rõ</p>
            </div>
            <div className="bg-white/20 backdrop-blur p-4 rounded-lg">
              <p className="text-3xl font-bold">A</p>
              <p className="text-lg">Đánh giá</p>
              <p className="text-sm mt-2">Rất tốt, nên sửa 5-10%</p>
            </div>
          </div>

          <div className="space-y-4 text-white/90">
            <p className="text-lg">
              <strong>✅ Điểm mạnh lớn nhất:</strong> Phương pháp tiếp cận (ontology + multi-hop + rule validator) là <strong>hệ thống, đầy đủ, khả thi</strong>. Kết quả định lượng (Local 90%, Multi-hop 100%) rất thuyết phục.
            </p>
            <p className="text-lg">
              <strong>⚠️ Điểm yếu lớn nhất:</strong> Thiếu DIAGRAM kiến trúc, test set nhỏ (10 cases chính), ground truth chưa validate expert. Có thể được chấp nhận nếu sửa CẤP 1.
            </p>
            <p className="text-lg">
              <strong>🎯 Khuyến nghị cuối cùng:</strong> Luận văn đủ chất lượng để nộp, nhưng nên sửa tối thiểu 3 mục CẤP 1 (diagram, rút gọn chương 1, metadata JSON) để tăng điểm từ A lên A+.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ThesisReviewDashboard;

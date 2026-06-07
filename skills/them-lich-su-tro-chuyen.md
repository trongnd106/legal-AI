# Hướng dẫn: Thêm tính năng Lịch sử Trò chuyện & Cập nhật nút Mic

> Tài liệu này mô tả các thay đổi cần thực hiện trên UI **Luật Lao Động AI** để bổ sung khu vực lịch sử trò chuyện trong sidebar và cập nhật icon nút gửi giọng nói.

---

## 1. Tổng quan thay đổi

| Khu vực | Thay đổi |
|---|---|
| Sidebar | Thêm section **Lịch sử trò chuyện** bên dưới nav items |
| Sidebar | Thêm nút **+ Cuộc trò chuyện mới** |
| Sidebar | Thêm danh sách các cuộc trò chuyện cũ |
| Input Bar | Thay icon `mic` (Lucide) bằng icon `mic` kiểu mới theo ảnh thiết kế |

---

## 2. Thay đổi Sidebar — Thêm Lịch sử trò chuyện

### 2.1 Sơ đồ bố cục sidebar sau khi cập nhật

```
┌─────────────────────────────┐
│  [⚖ Luật Lao Động AI]       │  ← Logo, padding 16px top
├─────────────────────────────┤
│  [💬 Hỏi đáp trực tuyến]   │  ← nav-item, active = bg đậm
│  [🗄 Kho dữ liệu luật]     │  ← nav-item bình thường
├─────────────────────────────┤  ← divider ngầm (margin)
│  LỊCH SỬ TRÒ CHUYỆN        │  ← label nhỏ, chữ hoa, mờ
│                             │
│  [+ Cuộc trò chuyện mới]   │  ← nút tạo mới, dashed border
│                             │
│  [💬 Thử việc tối đa bao...] ← history-item đang active
│  [💬 Chế độ thai sản nam 2..]│ ← history-item bình thường
│  [💬 Thông báo nghỉ việc tr.]│ ← history-item bình thường
│                             │
│  (scroll nếu quá nhiều)     │
└─────────────────────────────┘
```

### 2.2 HTML — Cập nhật cấu trúc `<aside>`

Thêm block sau vào bên dưới `<nav class="sidebar-nav">`:

```html
<aside class="sidebar">
  <!-- Logo (giữ nguyên) -->
  <div class="sidebar-logo">
    <span class="logo-icon">⚖️</span>
    <span class="logo-text">Luật Lao Động AI</span>
  </div>

  <!-- Nav chính (giữ nguyên) -->
  <nav class="sidebar-nav">
    <a class="nav-item active" href="#chat" data-tab="chat">
      <i data-lucide="message-square" size="16"></i>
      Hỏi đáp trực tuyến
    </a>
    <a class="nav-item" href="#panel" data-tab="panel">
      <i data-lucide="database" size="16"></i>
      Kho dữ liệu luật
    </a>
  </nav>

  <!-- ✅ MỚI: Lịch sử trò chuyện -->
  <div class="history-section">

    <span class="history-label">Lịch sử trò chuyện</span>

    <button class="btn-new-chat" onclick="createNewChat()">
      <i data-lucide="plus" size="16"></i>
      Cuộc trò chuyện mới
    </button>

    <ul class="history-list" id="historyList">
      <!-- Render động bằng JS, hoặc hardcode mẫu: -->
      <li class="history-item active">
        <i data-lucide="message-square" size="14"></i>
        <span class="history-title">Thử việc tối đa bao lâu?</span>
      </li>
      <li class="history-item">
        <i data-lucide="message-square" size="14"></i>
        <span class="history-title">Chế độ thai sản nam 2...</span>
      </li>
      <li class="history-item">
        <i data-lucide="message-square" size="14"></i>
        <span class="history-title">Thông báo nghỉ việc tr...</span>
      </li>
    </ul>

  </div>
</aside>
```

### 2.3 CSS — Các class mới cần thêm

```css
/* ── Sidebar cần thêm overflow để history-list có thể scroll ── */
.sidebar {
  /* thêm vào rule hiện có: */
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── Khu vực lịch sử ── */
.history-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
  flex: 1;           /* chiếm phần còn lại của sidebar */
  min-height: 0;     /* quan trọng: cho phép flex-child scroll */
}

/* ── Label tiêu đề "LỊCH SỬ TRÒ CHUYỆN" ── */
.history-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.55);
  padding: 0 4px;
  margin-bottom: 2px;
}

/* ── Nút tạo cuộc trò chuyện mới ── */
.btn-new-chat {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  border: 1.5px dashed rgba(255, 255, 255, 0.45);
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.18s, border-color 0.18s;
  text-align: left;
}

.btn-new-chat:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.7);
}

/* ── Danh sách lịch sử ── */
.history-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;       /* scroll khi quá nhiều item */
  flex: 1;
}

/* ── Scrollbar style tối giản cho history-list ── */
.history-list::-webkit-scrollbar {
  width: 3px;
}
.history-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 3px;
}

/* ── Item lịch sử ── */
.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.75);
  font-size: 13px;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  overflow: hidden;
}

.history-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.history-item.active {
  background: rgba(0, 0, 0, 0.2);
  color: #fff;
  font-weight: 500;
}

/* ── Tiêu đề item: cắt bớt nếu dài ── */
.history-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

/* ── Icon trong item ── */
.history-item svg {
  flex-shrink: 0;
  opacity: 0.7;
}
.history-item.active svg {
  opacity: 1;
}
```

---

## 3. Cập nhật nút Mic trong Input Bar

### 3.1 Phân tích thay đổi

Nhìn vào ảnh thiết kế mới, vùng input bar góc phải có **3 phần tử** xếp ngang:

```
[🎤 icon mic]  [✦ icon AI/sparkle]  [⋮⋮ icon grid/menu]
```

Icon `mic` vẫn giữ nguyên vị trí nhưng được bo tròn và nằm cạnh hai icon phụ mới. Hai icon mới là:
- **`sparkles`** (Lucide) — gợi ý AI / phím tắt
- **`grid-2x2`** hoặc **`layout-grid`** (Lucide) — menu mở rộng

### 3.2 HTML — Thay thế nút mic cũ

**Trước (cũ):**
```html
<button class="icon-btn" title="Gửi bằng giọng nói"
  onclick="alert('Đang mở micro nhận diện giọng nói...')">
  <i data-lucide="mic" size="20"></i>
</button>
```

**Sau (mới) — thay toàn bộ phần cuối input bar:**
```html
<!-- Nhóm icon bên phải input -->
<div class="input-right-group">

  <button class="icon-btn" title="Gửi bằng giọng nói"
    onclick="alert('Đang mở micro nhận diện giọng nói...')">
    <i data-lucide="mic" size="20"></i>
  </button>

  <!-- ✅ MỚI: icon AI sparkle -->
  <button class="icon-btn" title="Gợi ý AI">
    <i data-lucide="sparkles" size="18"></i>
  </button>

  <!-- ✅ MỚI: icon grid menu — nút gửi chính bo tròn -->
  <button class="btn-send-grid" title="Gửi">
    <i data-lucide="grid-2x2" size="18"></i>
  </button>

</div>
```

> **Lưu ý:** Nếu icon `grid-2x2` không có trong phiên bản Lucide đang dùng, thay bằng `layout-grid` hoặc `table`.

### 3.3 CSS — Thêm style cho nhóm icon mới

```css
/* ── Nhóm icon bên phải input ── */
.input-right-group {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

/* ── Giữ nguyên style .icon-btn hiện có, chỉ bổ sung: ── */
.icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary, #666);
  transition: background 0.15s, color 0.15s;
}

.icon-btn:hover {
  background: var(--color-bg-main, #F5F5F5);
  color: var(--color-primary, #C0282D);
}

/* ── Nút gửi dạng grid (hình tròn đỏ, góc phải cùng) ── */
.btn-send-grid {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-primary, #C0282D);
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(192, 40, 45, 0.35);
  transition: background 0.2s, transform 0.1s;
  flex-shrink: 0;
}

.btn-send-grid:hover {
  background: #9B1E22;
}

.btn-send-grid:active {
  transform: scale(0.92);
}
```

### 3.4 Cập nhật HTML Input Bar đầy đủ

Cấu trúc `.chat-input-bar` sau khi tích hợp tất cả thay đổi:

```html
<div class="chat-input-bar">
  <!-- Icon đính kèm -->
  <button class="icon-btn" title="Đính kèm file">
    <i data-lucide="paperclip" size="20"></i>
  </button>

  <!-- Ô nhập liệu -->
  <input
    type="text"
    class="chat-input"
    id="chatInput"
    placeholder="Nhập câu hỏi về luật lao động của bạn tại đây..."
    onkeydown="if(event.key==='Enter') sendMessage()"
  />

  <!-- ✅ Nhóm icon bên phải (cập nhật) -->
  <div class="input-right-group">
    <button class="icon-btn" title="Gửi bằng giọng nói"
      onclick="alert('Đang mở micro nhận diện giọng nói...')">
      <i data-lucide="mic" size="20"></i>
    </button>
    <button class="icon-btn" title="Gợi ý AI">
      <i data-lucide="sparkles" size="18"></i>
    </button>
    <button class="btn-send-grid" title="Gửi" onclick="sendMessage()">
      <i data-lucide="grid-2x2" size="18"></i>
    </button>
  </div>
</div>
```

---

## 4. JavaScript — Quản lý lịch sử trò chuyện

```javascript
// ── Dữ liệu lịch sử (có thể lưu vào localStorage) ──
let chatHistory = [
  { id: 1, title: 'Thử việc tối đa bao lâu?',    active: true  },
  { id: 2, title: 'Chế độ thai sản nam 2...',     active: false },
  { id: 3, title: 'Thông báo nghỉ việc tr...',    active: false },
];

// ── Render danh sách lịch sử vào sidebar ──
function renderHistory() {
  const list = document.getElementById('historyList');
  if (!list) return;

  list.innerHTML = chatHistory.map(chat => `
    <li class="history-item ${chat.active ? 'active' : ''}"
        onclick="switchChat(${chat.id})">
      <i data-lucide="message-square" size="14"></i>
      <span class="history-title">${chat.title}</span>
    </li>
  `).join('');

  // Re-init Lucide icons sau khi render động
  if (window.lucide) lucide.createIcons();
}

// ── Chuyển sang cuộc trò chuyện khác ──
function switchChat(id) {
  chatHistory = chatHistory.map(c => ({ ...c, active: c.id === id }));
  renderHistory();
  // TODO: load nội dung cuộc trò chuyện tương ứng vào .chat-messages
}

// ── Tạo cuộc trò chuyện mới ──
function createNewChat() {
  const newId = Date.now();
  const newChat = { id: newId, title: 'Cuộc trò chuyện mới', active: true };

  // Deactivate all, thêm chat mới lên đầu
  chatHistory = [newChat, ...chatHistory.map(c => ({ ...c, active: false }))];
  renderHistory();

  // Xóa sạch vùng tin nhắn
  const messages = document.querySelector('.chat-messages');
  if (messages) messages.innerHTML = '';
}

// ── Cập nhật tiêu đề sau khi user gửi tin nhắn đầu tiên ──
function updateHistoryTitle(text) {
  const active = chatHistory.find(c => c.active);
  if (active && active.title === 'Cuộc trò chuyện mới') {
    active.title = text.length > 28 ? text.slice(0, 28) + '...' : text;
    renderHistory();
  }
}

// ── Gọi khi DOM sẵn sàng ──
document.addEventListener('DOMContentLoaded', () => {
  renderHistory();
});
```

---

## 5. Checklist tích hợp

- [ ] Thêm `.history-section` vào trong `<aside class="sidebar">`
- [ ] Thêm `overflow: hidden; flex-direction: column` vào `.sidebar`
- [ ] Copy toàn bộ CSS mục 2.3 vào stylesheet
- [ ] Thay nút mic đơn lẻ bằng `.input-right-group` chứa 3 icon
- [ ] Thêm CSS `.input-right-group`, `.btn-send-grid` vào stylesheet
- [ ] Thêm JS `renderHistory()`, `switchChat()`, `createNewChat()` vào script
- [ ] Gọi `lucide.createIcons()` sau mỗi lần render động history list
- [ ] (Tùy chọn) Lưu `chatHistory` vào `localStorage` để giữ dữ liệu khi reload

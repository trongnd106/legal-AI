# Luật Lao Động AI — Tài liệu Thiết kế Giao diện

> Mô tả chi tiết cách xây dựng ứng dụng chatbot tư vấn Luật Lao động với hai màn hình chính: **Chat** và **Kho dữ liệu luật (Panel)**.

---

## 1. Tổng quan hệ thống thiết kế

### 1.1 Bảng màu (Color Palette)

| Token | Giá trị | Mô tả |
|---|---|---|
| `--color-primary` | `#C0282D` | Đỏ chủ đạo — sidebar, nút gửi, tab active |
| `--color-primary-dark` | `#9B1E22` | Hover / active trên nền đỏ |
| `--color-sidebar-bg` | `#C0282D` | Toàn bộ thanh sidebar trái |
| `--color-sidebar-active` | `#9B1E22` | Mục menu đang được chọn |
| `--color-sidebar-text` | `#FFFFFF` | Chữ trên sidebar |
| `--color-bg-main` | `#F5F5F5` | Nền vùng nội dung chính |
| `--color-surface` | `#FFFFFF` | Card, bubble bot, input |
| `--color-user-bubble` | `#FFF8DC` | Bubble tin nhắn người dùng (vàng nhạt) |
| `--color-bot-bubble` | `#FFFFFF` | Bubble tin nhắn bot |
| `--color-text-primary` | `#1A1A1A` | Văn bản chính |
| `--color-text-secondary` | `#666666` | Meta-text, placeholder |
| `--color-border` | `#E0E0E0` | Viền card, input, tab |
| `--color-tab-active-line` | `#C0282D` | Gạch chân tab đang active |

### 1.2 Typography

| Role | Font | Weight | Size |
|---|---|---|---|
| Logo / Brand | `Be Vietnam Pro` hoặc `SVN-Gilroy` | 700 (Bold) | 18–20px |
| Heading sidebar | `Be Vietnam Pro` | 600 | 14px |
| Body / Bubble | `Be Vietnam Pro` | 400 | 14–15px |
| Meta (size, date) | `Be Vietnam Pro` | 400 | 12px |
| Placeholder | `Be Vietnam Pro` | 400 italic | 14px |

> **Lưu ý:** Ưu tiên font hỗ trợ tiếng Việt đầy đủ dấu. `Be Vietnam Pro` từ Google Fonts là lựa chọn tốt nhất.

### 1.3 Spacing & Radius

```
--spacing-xs:   4px
--spacing-sm:   8px
--spacing-md:  16px
--spacing-lg:  24px
--spacing-xl:  32px

--radius-sm:   6px
--radius-md:  12px
--radius-lg:  20px   ← bubble chat
--radius-card: 12px  ← card file
```

### 1.4 Shadow

```css
--shadow-card: 0 1px 4px rgba(0,0,0,0.08);
--shadow-input: 0 2px 8px rgba(0,0,0,0.06);
--shadow-btn-send: 0 4px 12px rgba(192,40,45,0.4);
```

---

## 2. Bố cục tổng thể (Layout)

### 2.1 Cấu trúc hai cột ngang

Toàn bộ ứng dụng là một `<div>` dùng `display: flex; height: 100vh; overflow: hidden`. Không bao giờ cuộn trang — chỉ vùng tin nhắn bên trong mới có scroll riêng.

```
┌──────────────────────────────────────────────────────────────┐
│  SIDEBAR · 130px · flex-shrink: 0                            │
│  background: #C0282D                                         │
│  ──────────────────────────────────────────────────────────  │
│  [⚖ Logo + Tên app]   ← padding 16px, font-weight 700       │
│                                                              │
│  [💬 Hỏi đáp trực tuyến]  ← nav-item active, bg đậm hơn    │
│  [🗄 Kho dữ liệu luật]    ← nav-item bình thường            │
│                                                              │
│  MAIN CONTENT · flex: 1 · display: flex · flex-direction: column
│  ┌──────────────────────────────────────────────────────┐   │
│  │  TAB BAR · height: 48px · border-bottom              │   │
│  │  [chat ←active, đường đỏ bên dưới]  [panel]         │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │                                                      │   │
│  │         TAB CONTENT · flex: 1 · overflow: hidden     │   │
│  │         (xem chi tiết mục 2.2 và 2.3)               │   │
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

- `display: flex; height: 100vh; overflow: hidden` — layout gốc, không scroll trang
- Sidebar: `width: 130px; flex-shrink: 0; background: var(--color-sidebar-bg)`
- Main: `flex: 1; display: flex; flex-direction: column; background: var(--color-bg-main)`

---

### 2.2 Chi tiết bố cục màn hình Chat — 4 tầng dọc

Vùng main khi ở tab **chat** chia thành 4 tầng chồng nhau theo chiều dọc. Tầng 1 và tầng 4 có chiều cao cố định; tầng 2 co giãn lấp đầy phần còn lại.

```
┌─────────────────────────────────────────────────────┐
│ TẦNG 1 — Tab Bar                  height: 48px      │
│ bg: #FFFFFF · border-bottom: 1px solid #E0E0E0      │
│ padding: 0 24px · display: flex · align: center     │
│                                                     │
│   [chat]──── (active, đường đỏ 2px bên dưới)       │
│   [panel]                                           │
├─────────────────────────────────────────────────────┤
│ TẦNG 2 — Vùng tin nhắn            flex: 1           │
│ bg: #F5F5F5 · overflow-y: auto                      │
│ padding: 24px · display: flex · flex-direction: col │
│ gap: 16px                                           │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ ROW BOT (justify: flex-start)                │   │
│  │ [avatar 36px tròn đỏ] [bubble trắng, shadow] │   │
│  │  gap: 8px · align: flex-start               │   │
│  │  bubble: border-radius 4px 20px 20px 20px   │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ ROW USER (flex-direction: row-reverse)       │   │
│  │ [bubble vàng #FFF8DC] [avatar 36px tròn xám]│   │
│  │  bubble: border-radius 20px 4px 20px 20px   │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ ROW BOT DÀI (có action buttons)              │   │
│  │ [avatar đỏ] [bubble trắng]                  │   │
│  │             ├─ <p> nội dung văn bản          │   │
│  │             ├─ <ul> danh sách bullet         │   │
│  │             └─ [📋 Sao chép] [⬇ Tải về file]│   │
│  │               display: flex · gap: 8px       │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│ TẦNG 3 — Input Bar                height: 72px      │
│ bg: #FFFFFF · border-top: 1px solid #E0E0E0         │
│ padding: 16px 24px · display: flex · align: center  │
│                                                     │
│ [📎 36px] [INPUT flex-1, h-28px, bo tròn] [🎤 36px] [▶ 44px tròn đỏ]
│            border-radius: 20px                      │
│                               box-shadow đỏ         │
└─────────────────────────────────────────────────────┘
```

**Quy tắc căn chỉnh trong vùng tin nhắn:**

| Thành phần | Vị trí | Chi tiết |
|---|---|---|
| Avatar bot | Trái, cố định trên đầu bubble | `align-items: flex-start`, không co giãn |
| Bubble bot | Bên phải avatar, tối đa 68% chiều rộng | `max-width: 68%` |
| Avatar user | Phải, cố định trên đầu bubble | `flex-direction: row-reverse` |
| Bubble user | Bên trái avatar (do row-reverse) | `max-width: 68%` |
| Action buttons | Bên trong bubble bot, dưới cùng | `margin-top: 16px`, viền xám nhạt |

---

### 2.3 Chi tiết bố cục màn hình Panel — 2 vùng dọc

Vùng main khi ở tab **panel** gồm Tab Bar (giống Chat) và phần nội dung bên dưới chia thành 2 vùng chồng nhau.

```
┌─────────────────────────────────────────────────────┐
│ TẦNG 1 — Tab Bar                  height: 48px      │
│ (giống màn hình Chat, nhưng tab "panel" active)     │
├─────────────────────────────────────────────────────┤
│ TẦNG 2 — Vùng nội dung            flex: 1           │
│ bg: #F5F5F5 · overflow-y: auto · padding: 24px      │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ UPLOAD ZONE               height: ~64px      │   │
│  │ display: flex · align: center · justify: ctr │   │
│  │ border: 2px dashed #E0E0E0                   │   │
│  │ border-radius: 12px · bg: #FFFFFF            │   │
│  │ margin-bottom: 24px                          │   │
│  │                                              │   │
│  │  [icon 📄⬆ 48px]  [Tải lên file luật mới]  │   │
│  │                    font-size: 18px · 600     │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  FILE GRID                                          │
│  display: grid                                      │
│  grid-template-columns: 1fr 1fr                     │
│  gap: 16px                                          │
│                                                     │
│  ┌──────────────────┐  ┌──────────────────────┐     │
│  │ FILE CARD        │  │ FILE CARD            │     │
│  │ height: 64px     │  │ height: 64px         │     │
│  │ display: flex    │  │ display: flex        │     │
│  │ align: center    │  │ align: center        │     │
│  │ gap: 16px        │  │ gap: 16px            │     │
│  │                  │  │                      │     │
│  │ [icon 36×40px]   │  │ [icon 36×40px]       │     │
│  │  PDF→bg đỏ nhạt  │  │  DOC→bg xám nhạt     │     │
│  │ [tên file        │  │ [tên file            │     │
│  │  meta: size·date]│  │  meta: size·date]    │     │
│  │ [⬇][👁] sát phải│  │ [⬇][👁] sát phải    │     │
│  └──────────────────┘  └──────────────────────┘     │
│  ┌──────────────────┐  ┌──────────────────────┐     │
│  │ FILE CARD        │  │ FILE CARD            │     │
│  │ ...              │  │ ...                  │     │
│  └──────────────────┘  └──────────────────────┘     │
│  (tiếp tục scroll)                                  │
└─────────────────────────────────────────────────────┘
```

**Cấu trúc bên trong một File Card:**

```
┌──────────────────────────────────────────────────────┐
│  display: flex · align-items: center · gap: 16px     │
│  padding: 16px · border-radius: 12px · bg: #FFFFFF   │
│  border: 1px solid #E0E0E0                           │
│                                                      │
│  ┌──────────┐  ┌───────────────────────┐  ┌───────┐  │
│  │ ICON     │  │ FILE INFO · flex: 1   │  │ BTNS  │  │
│  │ 36×40px  │  │ min-width: 0          │  │ flex  │  │
│  │ rx: 6px  │  │                       │  │ gap:4 │  │
│  │ PDF=đỏ   │  │ .file-name 14px 600   │  │ [⬇]  │  │
│  │ DOC=xám  │  │ overflow: ellipsis    │  │ [👁]  │  │
│  │          │  │ .file-meta 12px xám   │  │ 32px  │  │
│  └──────────┘  └───────────────────────┘  └───────┘  │
└──────────────────────────────────────────────────────┘
```

> **Lưu ý quan trọng:** `min-width: 0` trên `.file-info` là bắt buộc để `text-overflow: ellipsis` hoạt động đúng trong flex container. Nếu thiếu, tên file dài sẽ đẩy các icon ra ngoài card.

---

## 3. Sidebar

### 3.1 Cấu trúc HTML

```html
<aside class="sidebar">
  <!-- Logo -->
  <div class="sidebar-logo">
    <span class="logo-icon">⚖️</span>
    <span class="logo-text">Luật Lao Động AI</span>
  </div>

  <!-- Navigation -->
  <nav class="sidebar-nav">
    <a class="nav-item active" href="#chat">
      <span class="nav-icon">💬</span>
      Hỏi đáp trực tuyến
    </a>
    <a class="nav-item" href="#panel">
      <span class="nav-icon">🗄️</span>
      Kho dữ liệu luật
    </a>
  </nav>
</aside>
```

### 3.2 CSS

```css
.sidebar {
  width: 264px;
  background: var(--color-primary);
  color: var(--color-sidebar-text);
  display: flex;
  flex-direction: column;
  padding: var(--spacing-md);
  gap: var(--spacing-lg);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) 0;
  font-size: 18px;
  font-weight: 700;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 10px var(--spacing-md);
  border-radius: var(--radius-sm);
  color: rgba(255,255,255,0.85);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.nav-item:hover,
.nav-item.active {
  background: var(--color-sidebar-active);
  color: #fff;
}
```

---

## 4. Tab Bar

```html
<div class="tab-bar">
  <button class="tab active" data-tab="chat">chat</button>
  <button class="tab" data-tab="panel">panel</button>
</div>
```

```css
.tab-bar {
  display: flex;
  gap: var(--spacing-lg);
  padding: 0 var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.tab {
  padding: 14px 4px;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-tab-active-line);
}
```

---

## 5. Màn hình Chat

### 5.1 Bố cục

> Xem sơ đồ chi tiết tại **mục 2.2**. Tóm tắt nhanh:

```
┌──────────────────────────────────────────┐
│  Tab Bar · 48px · border-bottom          │
├──────────────────────────────────────────┤
│                                          │
│  [avatar đỏ] Bubble bot (trái)           │
│                                          │
│           Bubble user (phải) [avatar xám]│
│                                          │
│  [avatar đỏ] Bubble bot dài              │
│              [📋 Sao chép] [⬇ Tải file] │
│                                          │
├──────────────────────────────────────────┤
│  [📎] [Input · flex:1 · bo tròn] [🎤] [▶ tròn đỏ]
└──────────────────────────────────────────┘
```

### 5.2 Vùng tin nhắn

```html
<div class="chat-messages">

  <!-- Tin nhắn bot -->
  <div class="message bot">
    <div class="avatar bot-avatar">🤖</div>
    <div class="bubble bot-bubble">
      <p>Xin chào! Tôi có thể hỗ trợ gì cho bạn...</p>
    </div>
  </div>

  <!-- Tin nhắn user -->
  <div class="message user">
    <div class="bubble user-bubble">
      <p>Thời gian thử việc tối đa cho vị trí quản lý cấp cao là bao lâu?</p>
    </div>
    <div class="avatar user-avatar">👤</div>
  </div>

  <!-- Tin nhắn bot có nội dung dài + action buttons -->
  <div class="message bot">
    <div class="avatar bot-avatar">🤖</div>
    <div class="bubble bot-bubble">
      <p>Theo Điều 25 Luật Lao động năm 2019...</p>
      <ul>
        <li>Không quá 180 ngày...</li>
        <li>Không quá 180 ngày, hiện luật lao động...</li>
      </ul>
      <div class="bubble-actions">
        <button class="action-btn"><span>📋</span> Sao chép</button>
        <button class="action-btn"><span>⬇️</span> Tải về file</button>
      </div>
    </div>
  </div>

</div>
```

### 5.3 CSS Bubble

```css
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.message {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.user-avatar {
  background: var(--color-border);
}

.bubble {
  max-width: 68%;
  padding: var(--spacing-md);
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.6;
}

.bot-bubble {
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
  border-radius: 4px var(--radius-lg) var(--radius-lg) var(--radius-lg);
}

.user-bubble {
  background: var(--color-user-bubble);
  border-radius: var(--radius-lg) 4px var(--radius-lg) var(--radius-lg);
}

.bubble ul {
  padding-left: var(--spacing-md);
  margin: var(--spacing-sm) 0 0;
}

.bubble-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text-primary);
  transition: background 0.15s;
}

.action-btn:hover {
  background: #F0F0F0;
}
```

### 5.4 Input Bar

```html
<div class="chat-input-bar">
  <button class="input-icon-btn" title="Đính kèm">📎</button>
  <input
    type="text"
    class="chat-input"
    placeholder="Nhập câu hỏi về luật lao động của bạn tại đây..."
  />
  <button class="input-icon-btn" title="Giọng nói">🎤</button>
  <button class="btn-send" title="Gửi">➤</button>
</div>
```

```css
.chat-input-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.chat-input {
  flex: 1;
  padding: 10px var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  background: var(--color-bg-main);
  color: var(--color-text-primary);
  transition: border-color 0.2s;
}

.chat-input:focus {
  border-color: var(--color-primary);
}

.input-icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--color-text-secondary);
  border-radius: 50%;
  transition: background 0.15s;
}

.input-icon-btn:hover {
  background: var(--color-bg-main);
}

.btn-send {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  border: none;
  font-size: 18px;
  cursor: pointer;
  box-shadow: var(--shadow-btn-send);
  transition: background 0.2s, transform 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-send:hover {
  background: var(--color-primary-dark);
}

.btn-send:active {
  transform: scale(0.93);
}
```

---

## 6. Màn hình Panel — Kho dữ liệu luật

### 6.1 Bố cục

> Xem sơ đồ chi tiết tại **mục 2.3**. Tóm tắt nhanh:

```
┌──────────────────────────────────────────────────┐
│  Tab Bar · 48px (tab "panel" active)             │
├──────────────────────────────────────────────────┤
│  padding: 24px · overflow-y: auto                │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  [📄⬆]  Tải lên file luật mới           │    │
│  │  border: 2px dashed · height: ~64px      │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  grid · 2 cột · 1fr 1fr · gap: 16px             │
│  ┌────────────────┐  ┌──────────────────────┐    │
│  │ [icon][info][⬇👁]│  │ [icon][info][⬇👁]  │    │
│  │ 64px height    │  │ 64px height          │    │
│  └────────────────┘  └──────────────────────┘    │
│  ┌────────────────┐  ┌──────────────────────┐    │
│  │ ...            │  │ ...                  │    │
│  └────────────────┘  └──────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### 6.2 Upload Zone

```html
<div class="upload-zone">
  <div class="upload-icon">
    <span class="file-icon">📄</span>
    <span class="up-arrow">⬆</span>
  </div>
  <span class="upload-label">Tải lên file luật mới</span>
</div>
```

```css
.upload-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-xl);
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-card);
  cursor: pointer;
  background: var(--color-surface);
  transition: border-color 0.2s, background 0.2s;
  margin-bottom: var(--spacing-lg);
}

.upload-zone:hover {
  border-color: var(--color-primary);
  background: #FFF5F5;
}

.upload-label {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}
```

### 6.3 Grid File Cards

```html
<div class="file-grid">

  <div class="file-card">
    <div class="file-icon pdf">📄</div>
    <div class="file-info">
      <div class="file-name">Bộ luật Lao động 2019</div>
      <div class="file-meta">67.3 MB • Ngày 15/17/2021</div>
    </div>
    <div class="file-actions">
      <button class="file-btn" title="Tải xuống">⬇️</button>
      <button class="file-btn" title="Xem">👁️</button>
    </div>
  </div>

  <!-- Lặp lại cho các file khác -->

</div>
```

```css
.file-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.file-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s;
}

.file-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.file-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: #F0F0F0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.file-icon.pdf {
  background: #FDECEA;  /* đỏ nhạt cho PDF */
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.file-actions {
  display: flex;
  gap: 4px;
}

.file-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: var(--radius-sm);
  font-size: 16px;
  color: var(--color-text-secondary);
  transition: background 0.15s, color 0.15s;
}

.file-btn:hover {
  background: var(--color-bg-main);
  color: var(--color-primary);
}
```

---

## 7. CSS Variables gốc (Root)

```css
:root {
  --color-primary:        #C0282D;
  --color-primary-dark:   #9B1E22;
  --color-sidebar-bg:     #C0282D;
  --color-sidebar-active: #9B1E22;
  --color-sidebar-text:   #FFFFFF;
  --color-bg-main:        #F5F5F5;
  --color-surface:        #FFFFFF;
  --color-user-bubble:    #FFF8DC;
  --color-bot-bubble:     #FFFFFF;
  --color-text-primary:   #1A1A1A;
  --color-text-secondary: #666666;
  --color-border:         #E0E0E0;
  --color-tab-active-line:#C0282D;

  --spacing-xs:  4px;
  --spacing-sm:  8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;

  --radius-sm:   6px;
  --radius-md:  12px;
  --radius-lg:  20px;
  --radius-card:12px;

  --shadow-card:     0 1px 4px rgba(0,0,0,0.08);
  --shadow-input:    0 2px 8px rgba(0,0,0,0.06);
  --shadow-btn-send: 0 4px 12px rgba(192,40,45,0.4);
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Be Vietnam Pro', sans-serif;
  background: var(--color-bg-main);
  color: var(--color-text-primary);
  height: 100vh;
  overflow: hidden;
}
```

---

## 8. Responsive (Mobile)

```css
@media (max-width: 768px) {
  .sidebar {
    display: none;  /* ẩn sidebar, thay bằng bottom nav */
  }

  .file-grid {
    grid-template-columns: 1fr;
  }

  .bubble {
    max-width: 88%;
  }
}
```

---

## 9. JavaScript — Chuyển tab

```javascript
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    // Deactivate all
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    // Activate clicked
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');

    // Sync sidebar nav
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.tab === tab.dataset.tab);
    });
  });
});
```

---

## 10. Checklist hoàn thiện

- [ ] Import font `Be Vietnam Pro` từ Google Fonts
- [ ] Khai báo đủ CSS Variables trong `:root`
- [ ] Sidebar luôn hiển thị trên desktop, ẩn trên mobile
- [ ] Tab switching hoạt động mượt mà với CSS transition
- [ ] Bot avatar dùng màu đỏ chủ đạo `--color-primary`
- [ ] User bubble dùng màu vàng nhạt `#FFF8DC`
- [ ] Nút gửi (send) có border-radius 50% và box-shadow đỏ
- [ ] Upload zone có dashed border, hover đổi màu viền đỏ
- [ ] File card PDF có icon nền đỏ nhạt, file thường nền xám
- [ ] Scrollbar vùng chat được style tối giản
- [ ] Action buttons (Sao chép / Tải về file) trong bubble bot

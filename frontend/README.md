# Luật Lao Động AI — Frontend (Next.js)

Giao diện web theo spec `skills/luat-lao-dong-ai-ui-spec.md`, xây bằng **Next.js 15** (App Router + TypeScript).

## Cấu trúc

```
frontend/
├── app/
│   ├── layout.tsx       # Font Be Vietnam Pro, metadata
│   ├── page.tsx         # Trang chính
│   └── globals.css      # Design tokens + toàn bộ CSS
├── components/
│   ├── AppShell.tsx     # Layout + tab state
│   ├── Sidebar.tsx
│   ├── TabBar.tsx
│   ├── ChatPanel.tsx    # Hỏi đáp, mic, copy/tải
│   ├── DocumentPanel.tsx
│   ├── PreviewModal.tsx
│   └── ToastProvider.tsx
├── lib/api.ts           # REST client (proxy qua Next.js)
└── types/
```

## Chạy development

**Yêu cầu Node.js >= 18.18** (khuyến nghị Node 20 LTS). Next.js 15 không chạy trên Node 12/14.

```bash
cd frontend
nvm use          # đọc .nvmrc → Node 20
npm install
npm run dev      # → http://localhost:3000
```

Nếu `nvm use` báo chưa cài Node 20:

```bash
nvm install 20
nvm use 20
```

Cần **2 terminal** — API backend và Next.js frontend:

```bash
# Terminal 1 — API (repo root)
pip install -r api/requirements.txt
python -m api.main
# → http://localhost:8000

# Terminal 2 — Next.js (frontend/)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

Mở trình duyệt: **http://localhost:3000**

Next.js proxy `/api/*` sang `http://127.0.0.1:8000` (cấu hình trong `next.config.ts`, đổi qua biến `API_URL`).

## GraphRAG (tab Chat)

```bash
pip install -e packages/graphrag
graphrag index --root data/labor-law
```

## Production

```bash
cd frontend
npm run build
npm start
```

Đặt `API_URL` trỏ tới FastAPI backend khi deploy.

## Tính năng

- Tab **Chat**: GraphRAG local/global search, bubble, sao chép/tải, mic (Web Speech API)
- Tab **Panel**: danh sách văn bản, upload, xem trước, tải xuống
- Responsive: sidebar ẩn trên mobile

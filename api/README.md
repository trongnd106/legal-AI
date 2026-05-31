# Luật Lao Động AI — API

FastAPI backend phục vụ frontend và GraphRAG query.

## Cài đặt

```bash
# Từ thư mục gốc repo
pip install -r api/requirements.txt

# Để tab Chat hoạt động (GraphRAG + query/)
pip install -e packages/graphrag
```

## Chạy

```bash
python -m api.main
# hoặc
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Mở **http://localhost:8000** — chỉ API REST.

Frontend Next.js chạy riêng:

```bash
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

## Index GraphRAG (bắt buộc cho Chat)

```bash
graphrag index --root data/labor-law
```

Khi chưa index, `/api/health` trả `graphrag_ready: false` và `/api/chat` trả 503.

## Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/` | Giao diện web |
| GET | `/api/health` | Trạng thái server + GraphRAG |
| POST | `/api/chat` | `{ "question", "mode": "local\|global", "domain" }` |
| GET | `/api/documents` | Danh sách văn bản pháp luật |
| GET | `/api/documents/{id}/preview` | Xem trước nội dung |
| GET | `/api/documents/{id}/download` | Tải file |
| POST | `/api/documents/upload` | Upload văn bản mới |

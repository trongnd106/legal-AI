"""
api/main.py — FastAPI server phục vụ frontend + GraphRAG query.

Chạy:
  pip install -r api/requirements.txt
  python -m api.main

Hoặc:
  uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, contract, documents, sessions
from api.services.graph_loader import artifacts_available

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Luật Lao Động AI",
    description="API hỏi đáp luật lao động + kho dữ liệu văn bản",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def keep_alive_header(request, call_next):
    """Trả header Keep-Alive tường minh để Next.js proxy biết TTL socket."""
    response = await call_next(request)
    response.headers["Connection"] = "keep-alive"
    response.headers["Keep-Alive"] = "timeout=75"
    return response

app.include_router(chat.router)
app.include_router(contract.router)
app.include_router(documents.router)
app.include_router(sessions.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "graphrag_ready": artifacts_available(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        loop="asyncio",
        # Next.js proxy giữ socket trong pool; nếu uvicorn đóng socket sớm hơn
        # Node.js tái sử dụng nó → ECONNRESET. 75s > thời gian đọc câu trả lời.
        timeout_keep_alive=75,
    )

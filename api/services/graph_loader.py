"""GraphLoader singleton — cache loader sau lần load đầu."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from api.config import LABOR_LAW_ROOT

logger = logging.getLogger(__name__)


def artifacts_available() -> bool:
    """Kiểm tra có output GraphRAG artifacts chưa."""
    try:
        from query.loader import GraphLoader
    except ImportError:
        return False
    return GraphLoader.artifacts_available(LABOR_LAW_ROOT)


@lru_cache(maxsize=1)
def get_loader():
    """Load GraphLoader một lần; raise nếu chưa index.

    NOTE: Hàm này gọi asyncio.run() bên trong và phải được gọi từ non-async context
    (hoặc thông qua get_loader_async() khi trong event loop).
    """
    try:
        from query.loader import GraphLoader
    except ImportError as exc:
        raise FileNotFoundError(
            "GraphRAG chưa cài đặt. Chạy: pip install -e packages/graphrag"
        ) from exc

    loader = GraphLoader(str(LABOR_LAW_ROOT))
    loader.load()
    logger.info("GraphLoader ready: %s", loader.artifacts_dir)
    return loader


async def get_loader_async():
    """Async wrapper — chạy get_loader() trong thread pool để không block event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_loader)


def clear_loader_cache() -> None:
    get_loader.cache_clear()

"""GraphLoader singleton — cache loader sau lần load đầu."""

from __future__ import annotations

import logging
from functools import lru_cache

from api.config import LABOR_LAW_ROOT

logger = logging.getLogger(__name__)


def artifacts_available() -> bool:
    """Kiểm tra có output GraphRAG artifacts chưa."""
    out = LABOR_LAW_ROOT / "output"
    if not out.exists():
        return False
    candidates = sorted(out.glob("*/artifacts/create_final_entities.parquet"))
    return bool(candidates)


@lru_cache(maxsize=1)
def get_loader():
    """Load GraphLoader một lần; raise nếu chưa index."""
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


def clear_loader_cache() -> None:
    get_loader.cache_clear()

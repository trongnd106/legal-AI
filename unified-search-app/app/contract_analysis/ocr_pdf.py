# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""OCR PDF scan bằng PaddleOCR + render trang qua PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ocr_singleton: Any = None


def _get_paddle_ocr():
    """Khởi tạo PaddleOCR một lần (model nặng)."""
    global _ocr_singleton
    if _ocr_singleton is not None:
        return _ocr_singleton
    try:
        from paddleocr import PaddleOCR
    except ImportError as e:
        msg = (
            "Chưa cài PaddleOCR. Chạy: cd unified-search-app && uv sync --extra ocr "
            "(hoặc pip install paddlepaddle paddleocr pymupdf opencv-python-headless)."
        )
        raise ImportError(msg) from e

    try:
        _ocr_singleton = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)
    except Exception:
        logger.warning("PaddleOCR lang=vi thất bại, thử lang=en.")
        _ocr_singleton = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr_singleton


def _pixmap_to_numpy(pix: Any):
    import numpy as np

    h, w = pix.height, pix.width
    n = pix.n
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w, n)
    if n == 4:
        arr = arr[:, :, :3]
    return arr


def _ocr_lines_from_image(img_array: Any) -> str:
    ocr = _get_paddle_ocr()
    result = ocr.ocr(img_array, cls=True)
    if not result:
        return ""
    lines: list[str] = []
    pages = result if isinstance(result, list) else []
    first = pages[0] if pages else None
    if first is None:
        return ""
    for item in first:
        if item is None or len(item) < 2:
            continue
        txt_box = item[1]
        if txt_box is None:
            continue
        if isinstance(txt_box, (list, tuple)) and len(txt_box) >= 1:
            lines.append(str(txt_box[0]))
        else:
            lines.append(str(txt_box))
    return "\n".join(lines)


def extract_pdf_text_paddleocr(path: str | Path, *, zoom: float = 2.0) -> tuple[str, list[dict[str, str | int]], int]:
    """Render từng trang PDF sang ảnh và OCR bằng PaddleOCR."""
    try:
        import fitz
    except ImportError as e:
        msg = "Cần PyMuPDF (pymupdf). Cài: uv sync --extra ocr"
        raise ImportError(msg) from e

    path = Path(path)
    doc = fitz.open(path)
    mat = fitz.Matrix(zoom, zoom)
    parts: list[str] = []
    page_records: list[dict[str, str | int]] = []
    try:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = _pixmap_to_numpy(pix)
            text = _ocr_lines_from_image(img)
            parts.append(text)
            page_records.append({"page_num": i + 1, "text": text})
    finally:
        doc.close()

    raw = "\n\n".join(parts)
    return raw, page_records, len(page_records)


def paddleocr_available() -> bool:
    try:
        import paddleocr  # noqa: F401

        import fitz  # noqa: F401

        return True
    except ImportError:
        return False

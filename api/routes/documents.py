"""Routes documents — kho dữ liệu luật."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.config import (
    METADATA_PATH,
    NORMALIZED_DIR,
    PREVIEW_MAX_CHARS,
    REPO_ROOT,
    SLUG_TO_SO_HIEU,
    SO_HIEU_TO_SLUG,
    UPLOADS_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["documents"])

ALLOWED_EXT = {".txt", ".pdf", ".doc", ".docx"}


class DocumentItem(BaseModel):
    id: str
    ten: str
    so_hieu: str
    loai: str
    tinh_trang: str
    ngay_hieu_luc: str | None = None
    ngay_ban_hanh: str | None = None
    size_bytes: int
    extension: str
    updated_at: str | None = None
    source: str  # "indexed" | "upload"


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class PreviewResponse(BaseModel):
    id: str
    ten: str
    content: str
    truncated: bool


class UploadResponse(BaseModel):
    message: str
    filename: str
    path: str


def _load_metadata() -> dict:
    if not METADATA_PATH.exists():
        return {}
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def _resolve_path(doc_id: str) -> Path | None:
    """doc_id = slug (BLLĐ_2019) hoặc so_hieu URL-encoded."""
    slug = doc_id
    if doc_id in SLUG_TO_SO_HIEU:
        slug = doc_id
    elif doc_id in SO_HIEU_TO_SLUG:
        slug = SO_HIEU_TO_SLUG[doc_id]
    else:
        # thử decode slug trực tiếp
        for s in SO_HIEU_TO_SLUG.values():
            if s == doc_id:
                slug = s
                break

    norm = NORMALIZED_DIR / f"{slug}.txt"
    if norm.exists():
        return norm

    # uploads
    for p in UPLOADS_DIR.glob("*") if UPLOADS_DIR.exists() else []:
        if p.stem == doc_id or p.name == doc_id:
            return p
    return None


def _build_document_list() -> list[DocumentItem]:
    meta = _load_metadata()
    docs: list[DocumentItem] = []

    for so_hieu, info in meta.items():
        slug = SO_HIEU_TO_SLUG.get(so_hieu, so_hieu.replace("/", "_"))
        norm_path = NORMALIZED_DIR / f"{slug}.txt"
        size = norm_path.stat().st_size if norm_path.exists() else 0
        mtime = (
            datetime.fromtimestamp(norm_path.stat().st_mtime, tz=timezone.utc).date().isoformat()
            if norm_path.exists()
            else info.get("ngay_hieu_luc")
        )
        docs.append(
            DocumentItem(
                id=slug,
                ten=info.get("ten", so_hieu),
                so_hieu=so_hieu,
                loai=info.get("loai", ""),
                tinh_trang=info.get("tinh_trang", "con_hieu_luc"),
                ngay_hieu_luc=info.get("ngay_hieu_luc"),
                ngay_ban_hanh=info.get("ngay_ban_hanh"),
                size_bytes=size,
                extension="txt",
                updated_at=mtime,
                source="indexed",
            )
        )

    if UPLOADS_DIR.exists():
        indexed_names = {d.ten for d in docs}
        for p in sorted(UPLOADS_DIR.iterdir()):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            docs.append(
                DocumentItem(
                    id=p.stem,
                    ten=p.name,
                    so_hieu=p.stem,
                    loai="upload",
                    tinh_trang="cho_xu_ly",
                    size_bytes=p.stat().st_size,
                    extension=p.suffix.lstrip(".") or "txt",
                    updated_at=datetime.fromtimestamp(
                        p.stat().st_mtime, tz=timezone.utc
                    ).date().isoformat(),
                    source="upload",
                )
            )

    docs.sort(key=lambda d: (d.source != "indexed", d.ten))
    return docs


@router.get("/documents", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return DocumentListResponse(documents=_build_document_list())


@router.get("/documents/{doc_id}/preview", response_model=PreviewResponse)
def preview_document(doc_id: str) -> PreviewResponse:
    path = _resolve_path(doc_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy văn bản")

    meta = _load_metadata()
    slug = doc_id
    so_hieu = SLUG_TO_SO_HIEU.get(doc_id, doc_id)
    ten = meta.get(so_hieu, {}).get("ten", path.name)

    if path.suffix.lower() != ".txt":
        return PreviewResponse(
            id=doc_id,
            ten=ten,
            content=(
                f"File {path.name} ({path.suffix}) — "
                "xem trước chỉ hỗ trợ .txt. Dùng nút tải xuống."
            ),
            truncated=False,
        )

    text = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > PREVIEW_MAX_CHARS
    if truncated:
        text = text[:PREVIEW_MAX_CHARS] + "\n\n… (đã cắt bớt, tải file để xem đầy đủ)"

    return PreviewResponse(id=doc_id, ten=ten, content=text, truncated=truncated)


@router.get("/documents/{doc_id}/download")
def download_document(doc_id: str):
    path = _resolve_path(doc_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy văn bản")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Thiếu tên file")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ. Chấp nhận: {', '.join(sorted(ALLOWED_EXT))}",
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS_DIR / Path(file.filename).name

    # tránh ghi đè — thêm timestamp nếu trùng
    if dest.exists():
        stem = dest.stem
        dest = UPLOADS_DIR / f"{stem}_{int(datetime.now().timestamp())}{ext}"

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File quá lớn (tối đa 50MB)")

    dest.write_bytes(content)

    return UploadResponse(
        message=(
            "Đã lưu file. Để đưa vào kho luật: copy vào data/txt/ rồi chạy "
            "python3 scripts/01_prepare_data.py && graphrag index --root data/labor-law"
        ),
        filename=dest.name,
        path=str(dest.relative_to(REPO_ROOT)),
    )

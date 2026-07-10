"""Routes phân tích hợp đồng lao động — POST /api/contract/analyze."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from collections.abc import AsyncGenerator
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Thêm unified-search-app/app vào sys.path để import contract_analysis
_APP_DIR = Path(__file__).resolve().parent.parent.parent / "unified-search-app" / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

router = APIRouter(prefix="/api", tags=["contract"])

ALLOWED_EXT = {".txt", ".pdf", ".doc", ".docx"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


class ContractAnalysisResponse(BaseModel):
    markdown_report: str
    compliance_score: float
    filename: str
    num_clauses: int
    num_violations: int
    num_high_risk: int
    missing_mandatory: list[str]
    session_id: str


@router.post("/contract/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    file: UploadFile = File(...),
    wage_region: str = Form(default="IV"),
    skip_llm_review: bool = Form(default=False),
) -> ContractAnalysisResponse:
    """
    Phân tích hợp đồng lao động từ file upload.

    - **file**: PDF, DOCX hoặc TXT (tối đa 20 MB)
    - **wage_region**: Vùng lương tối thiểu I/II/III/IV (mặc định IV)
    - **skip_llm_review**: Bỏ qua LLM review batch để tiết kiệm thời gian
    """
    try:
        from contract_analysis.pipeline import run_contract_analysis
    except ImportError as exc:
        logger.error("Không import được contract_analysis: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Module phân tích hợp đồng chưa khả dụng. "
                "Kiểm tra unified-search-app/app có trong PYTHONPATH."
            ),
        ) from exc

    if not file.filename:
        raise HTTPException(status_code=400, detail="Thiếu tên file.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ. Chấp nhận: {', '.join(sorted(ALLOWED_EXT))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File quá lớn (tối đa 20 MB).")

    # Load GraphLoader (tái dùng cache từ chat service)
    try:
        from api.services.graph_loader import get_loader_async
        loader = await get_loader_async()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Lỗi load GraphLoader: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="GraphRAG chưa sẵn sàng. Chạy index trước.",
        ) from exc

    config = loader.config
    text_units = loader.text_units

    if config is None or text_units is None:
        raise HTTPException(
            status_code=503,
            detail="GraphRAG artifacts chưa đủ (config hoặc text_units bị thiếu).",
        )

    root_dir = str(loader.root_dir)

    try:
        if ext == ".txt":
            raw_text = content.decode("utf-8", errors="replace")
            result = await run_contract_analysis(
                config=config,
                text_units=text_units,
                raw_contract_text=raw_text,
                filename=file.filename,
                wage_region=wage_region.upper(),
                skip_llm_review=skip_llm_review,
                persist_neo4j=False,
                root_dir=root_dir,
            )
        else:
            # PDF / DOCX — lưu tạm vào tempfile rồi load
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                result = await run_contract_analysis(
                    config=config,
                    text_units=text_units,
                    file_path=tmp_path,
                    filename=file.filename,
                    wage_region=wage_region.upper(),
                    skip_llm_review=skip_llm_review,
                    persist_neo4j=False,
                    root_dir=root_dir,
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    except Exception as exc:
        exc_str = str(exc)
        logger.exception("Lỗi phân tích hợp đồng: %s", exc_str[:300])
        if "RateLimitError" in exc_str or "429" in exc_str:
            raise HTTPException(
                status_code=503,
                detail="Model AI đang quá tải, vui lòng thử lại sau 1–2 phút.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi phân tích: {exc_str[:400]}",
        ) from exc

    from contract_analysis.schema import ContractIssue

    all_issues: list[ContractIssue] = []
    for ca in result.per_clause:
        all_issues.extend(ca.rule_issues + ca.llm_issues)
    by_sev = Counter(i.severity for i in all_issues)

    return ContractAnalysisResponse(
        markdown_report=result.markdown_report or "",
        compliance_score=result.compliance_score,
        filename=file.filename,
        num_clauses=len(result.clauses),
        num_violations=by_sev.get("VIOLATION", 0),
        num_high_risk=by_sev.get("HIGH_RISK", 0),
        missing_mandatory=list(result.missing_mandatory),
        session_id=result.analysis_session_id or "",
    )


async def _stream_contract_analysis(
    file: UploadFile,
    wage_region: str,
    skip_llm_review: bool,
) -> AsyncGenerator[str, None]:
    """SSE generator — yield progress events rồi kết quả cuối cùng."""
    try:
        from contract_analysis.pipeline import run_contract_analysis
    except ImportError as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return

    if not file.filename:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Thiếu tên file'}, ensure_ascii=False)}\n\n"
        return

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Định dạng không hỗ trợ: {ext}'}, ensure_ascii=False)}\n\n"
        return

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        yield f"data: {json.dumps({'type': 'error', 'message': 'File quá lớn (tối đa 20 MB)'}, ensure_ascii=False)}\n\n"
        return

    try:
        from api.services.graph_loader import get_loader_async
        loader = await get_loader_async()
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        return

    config = loader.config
    text_units = loader.text_units
    if config is None or text_units is None:
        yield f"data: {json.dumps({'type': 'error', 'message': 'GraphRAG chưa sẵn sàng'}, ensure_ascii=False)}\n\n"
        return

    root_dir = str(loader.root_dir)
    progress_queue: asyncio.Queue[str] = asyncio.Queue()

    async def progress_callback(msg: str) -> None:
        await progress_queue.put(msg)

    analysis_task = asyncio.create_task(_run_analysis(
        run_contract_analysis, config, text_units, ext, content,
        file, wage_region, skip_llm_review, root_dir, progress_callback,
    ))

    while True:
        done = analysis_task.done()
        while not progress_queue.empty():
            msg = await progress_queue.get()
            yield f"data: {json.dumps({'type': 'progress', 'message': msg}, ensure_ascii=False)}\n\n"

        if done:
            break
        await asyncio.sleep(0.1)

    try:
        result = analysis_task.result()
    except Exception as exc:
        exc_str = str(exc)
        logger.exception("Lỗi phân tích hợp đồng (stream): %s", exc_str[:300])
        yield f"data: {json.dumps({'type': 'error', 'message': exc_str[:400]}, ensure_ascii=False)}\n\n"
        return

    from contract_analysis.schema import ContractIssue

    all_issues: list[ContractIssue] = []
    for ca in result.per_clause:
        all_issues.extend(ca.rule_issues + ca.llm_issues)
    by_sev = Counter(i.severity for i in all_issues)

    done_event = {
        "type": "done",
        "markdown_report": result.markdown_report or "",
        "compliance_score": result.compliance_score,
        "filename": file.filename,
        "num_clauses": len(result.clauses),
        "num_violations": by_sev.get("VIOLATION", 0),
        "num_high_risk": by_sev.get("HIGH_RISK", 0),
        "missing_mandatory": list(result.missing_mandatory),
        "session_id": result.analysis_session_id or "",
    }
    yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"


async def _run_analysis(
    run_contract_analysis,
    config,
    text_units,
    ext,
    content,
    file,
    wage_region,
    skip_llm_review,
    root_dir,
    progress_callback,
):
    if ext == ".txt":
        raw_text = content.decode("utf-8", errors="replace")
        return await run_contract_analysis(
            config=config, text_units=text_units,
            raw_contract_text=raw_text, filename=file.filename,
            wage_region=wage_region.upper(), skip_llm_review=skip_llm_review,
            persist_neo4j=False, root_dir=root_dir,
            progress_callback=progress_callback,
        )
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return await run_contract_analysis(
                config=config, text_units=text_units,
                file_path=tmp_path, filename=file.filename,
                wage_region=wage_region.upper(), skip_llm_review=skip_llm_review,
                persist_neo4j=False, root_dir=root_dir,
                progress_callback=progress_callback,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


@router.post("/contract/analyze/stream")
async def analyze_contract_stream(
    file: UploadFile = File(...),
    wage_region: str = Form(default="IV"),
    skip_llm_review: bool = Form(default=False),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_contract_analysis(file, wage_region, skip_llm_review),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

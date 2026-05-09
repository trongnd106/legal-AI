#!/usr/bin/env python3
# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License.

"""GraphRAG query API + Ragas evaluation (Gemini as judge).

See ``my-docs/ragas_graphrag_benchmark_guide.md`` for background.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import graphrag.api as api
import pandas as pd
from graphrag.cli.query import _resolve_output_files
from graphrag.config.load_config import load_config

logger = logging.getLogger(__name__)


def _resolve_cli_path_before_chdir(path: Path) -> Path:
    """Anchor relative paths to cwd before GraphRAG ``load_config`` calls ``os.chdir``."""
    expanded = path.expanduser()
    return (
        expanded.resolve()
        if expanded.is_absolute()
        else (Path.cwd() / expanded).resolve()
    )


TEXTISH_COLUMNS = (
    "full_content",
    "description",
    "text",
    "summary",
    "title",
    "content",
    "name",
    "human_readable_id",
    "report",
)


def _response_to_text(response: str | dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict | list):
        return json.dumps(response, ensure_ascii=False, indent=2)[:50_000]
    return str(response)


def _row_to_context_snippet(row: pd.Series, max_chars: int) -> str:
    parts: list[str] = []
    for col in row.index:
        val = row[col]
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        s = str(val).strip()
        if len(s) < 12:
            continue
        # Prefer known text columns first when building message
        label = str(col)
        parts.append(f"{label}: {s}")
    blob = "\n".join(parts) if parts else ""
    return blob[:max_chars] if blob else ""


def contexts_from_context_data(
    context_data: Any,
    *,
    max_chunks: int = 40,
    max_chars_per_chunk: int = 2500,
) -> list[str]:
    """Flatten GraphRAG ``context_data`` into text snippets for Ragas."""
    if context_data is None:
        return ["(no context)"]
    if isinstance(context_data, str) and context_data.strip():
        return [context_data.strip()[:max_chars_per_chunk]]
    if not isinstance(context_data, dict):
        return [str(context_data)[:max_chars_per_chunk]]

    out: list[str] = []
    # Stable key order for reproducibility
    for key in sorted(context_data.keys(), key=str):
        val = context_data[key]
        if val is None:
            continue
        if isinstance(val, pd.DataFrame):
            df = val
            if df.empty:
                continue
            # Prefer columns that usually hold prose
            ordered_cols = [c for c in TEXTISH_COLUMNS if c in df.columns] + [
                c for c in df.columns if c not in TEXTISH_COLUMNS
            ]
            sub = df[ordered_cols] if ordered_cols else df
            for _, row in sub.head(80).iterrows():
                snippet = _row_to_context_snippet(row, max_chars_per_chunk)
                if len(snippet) > 30:
                    out.append(snippet)
                if len(out) >= max_chunks:
                    return out
        elif isinstance(val, list | dict):
            s = json.dumps(val, ensure_ascii=False)[:max_chars_per_chunk]
            if len(s) > 30:
                out.append(s)
        else:
            s = str(val).strip()
            if len(s) > 30:
                out.append(s[:max_chars_per_chunk])
        if len(out) >= max_chunks:
            break

    return out if out else ["(empty context)"]


def load_questions(path: Path | None) -> list[tuple[str, str]]:
    """Load (question, reference) pairs from JSON or newline-delimited text."""
    if path is None:
        return [
            ("Tóm tắt các chủ đề chính trong tài liệu đã index.", ""),
            (
                "Nêu các khái niệm hoặc thực thể quan trọng và mối liên hệ giữa chúng.",
                "",
            ),
        ]
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, list):
            out: list[tuple[str, str]] = []
            for item in data:
                if isinstance(item, str):
                    out.append((item, ""))
                elif isinstance(item, dict):
                    q = item.get("question") or item.get("q") or item.get("user_input")
                    if not q:
                        msg = "JSON items need 'question' (or 'q' / 'user_input')"
                        raise ValueError(msg)
                    ref = item.get("reference") or item.get("ground_truth") or ""
                    out.append((str(q), str(ref)))
                else:
                    msg = "JSON list items must be str or object"
                    raise TypeError(msg)
            return out
        msg = "JSON questions file must be a list"
        raise ValueError(msg)
    # Plain text: one question per non-empty line
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return [(ln, "") for ln in lines]


def run_graphrag_query(
    root: Path,
    data_dir: Path | None,
    method: str,
    query: str,
    *,
    community_level: int,
    dynamic_community_selection: bool,
    response_type: str,
) -> tuple[str, dict[str, Any]]:
    """Execute one GraphRAG search and return textual answer plus context payloads."""
    cli_overrides: dict[str, Any] | None = None
    if data_dir is not None:
        cli_overrides = {"output_storage": {"base_dir": str(data_dir.resolve())}}
    config = load_config(root_dir=root.resolve(), cli_overrides=cli_overrides)

    m = method.lower().strip()
    if m == "global":
        tables = _resolve_output_files(
            config,
            ["entities", "communities", "community_reports"],
            [],
        )
        coro = api.global_search(
            config=config,
            entities=tables["entities"],
            communities=tables["communities"],
            community_reports=tables["community_reports"],
            community_level=community_level,
            dynamic_community_selection=dynamic_community_selection,
            response_type=response_type,
            query=query,
            verbose=False,
        )
    elif m == "local":
        tables = _resolve_output_files(
            config,
            [
                "communities",
                "community_reports",
                "text_units",
                "relationships",
                "entities",
            ],
            ["covariates"],
        )
        coro = api.local_search(
            config=config,
            entities=tables["entities"],
            communities=tables["communities"],
            community_reports=tables["community_reports"],
            text_units=tables["text_units"],
            relationships=tables["relationships"],
            covariates=tables.get("covariates"),
            community_level=community_level,
            response_type=response_type,
            query=query,
            verbose=False,
        )
    elif m == "drift":
        tables = _resolve_output_files(
            config,
            [
                "communities",
                "community_reports",
                "text_units",
                "relationships",
                "entities",
            ],
            [],
        )
        coro = api.drift_search(
            config=config,
            entities=tables["entities"],
            communities=tables["communities"],
            community_reports=tables["community_reports"],
            text_units=tables["text_units"],
            relationships=tables["relationships"],
            community_level=community_level,
            response_type=response_type,
            query=query,
            verbose=False,
        )
    elif m == "basic":
        tables = _resolve_output_files(config, ["text_units"], [])
        coro = api.basic_search(
            config=config,
            text_units=tables["text_units"],
            response_type=response_type,
            query=query,
            verbose=False,
        )
    else:
        msg = f"Unknown method {method!r}; use global, local, drift, or basic"
        raise ValueError(msg)

    response, context_data = asyncio.run(coro)
    return _response_to_text(response), context_data if isinstance(
        context_data, dict
    ) else {}


def run_ragas(
    samples: list[dict[str, Any]],
    *,
    eval_model: str,
    embedding_model: str,
    max_workers: int,
) -> Any:
    """Run Ragas Faithfulness and AnswerRelevancy using Gemini backends."""
    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
        GoogleGenerativeAIEmbeddings,
    )
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness
    from ragas.run_config import RunConfig

    evaluator_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=eval_model,
            temperature=0.1,
            max_tokens=2048,
        )
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(
            model=embedding_model,
            task_type="retrieval_document",
        )
    )
    dataset = EvaluationDataset.from_list(samples)
    rc = RunConfig(
        timeout=180,
        max_retries=5,
        max_wait=90,
        max_workers=max_workers,
        log_tenacity=True,
    )
    return evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(llm=evaluator_llm),
            AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=rc,
        show_progress=True,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Define and parse CLI flags."""
    epilog = """Prerequisites:
  uv sync --all-packages --group dev --group benchmark

Requires GOOGLE_API_KEY when running Ragas (--skip-eval omits judging).

Example:
  uv run python scripts/ragas_graphrag_benchmark.py --root ./my_project \\
    --questions scripts/ragas_benchmark_questions.example.json \\
    --method global --output-csv scores.csv"""

    p = argparse.ArgumentParser(
        description=__doc__,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--root",
        type=Path,
        required=True,
        help="GraphRAG project root (directory with settings.yaml / settings.yml).",
    )
    p.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Optional index output dir (override output_storage.base_dir).",
    )
    p.add_argument(
        "--method",
        default="global",
        choices=["global", "local", "drift", "basic"],
        help="GraphRAG query algorithm.",
    )
    p.add_argument(
        "--questions",
        type=Path,
        default=None,
        help="JSON array or .txt (one question per line). Omit for tiny built-in defaults.",
    )
    p.add_argument(
        "--community-level",
        type=int,
        default=2,
        help="Community level for global/local/drift.",
    )
    p.add_argument(
        "--dynamic-community-selection",
        action="store_true",
        help="Enable dynamic community selection (global search only).",
    )
    p.add_argument(
        "--response-type",
        default="Multiple Paragraphs",
        help="Passed through to GraphRAG query APIs.",
    )
    p.add_argument(
        "--max-context-chunks",
        type=int,
        default=40,
        help="Max context snippets passed to Ragas per question.",
    )
    p.add_argument(
        "--save-queries",
        type=Path,
        default=None,
        help="Optional path to save query results JSON (answers + context snippets).",
    )
    p.add_argument(
        "--save-query-snippet-chars",
        type=int,
        default=4000,
        help="Max characters per stored context snippet when using --save-queries.",
    )
    p.add_argument(
        "--save-query-max-context-snippets",
        type=int,
        default=20,
        help="Max context snippets per question stored in --save-queries JSON.",
    )
    p.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional path to save Ragas per-row scores CSV.",
    )
    p.add_argument(
        "--skip-eval",
        action="store_true",
        help="Only run GraphRAG queries; skip Gemini/Ragas scoring.",
    )
    p.add_argument(
        "--eval-model",
        default="gemini-2.0-flash",
        help="Gemini model id for Ragas judge LLM.",
    )
    p.add_argument(
        "--embedding-model",
        default="models/gemini-embedding-001",
        help="Gemini embedding model for AnswerRelevancy.",
    )
    p.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Ragas RunConfig max_workers (keep low on free tiers).",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Load questions, optionally query GraphRAG, optionally score with Ragas."""
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    project_root = args.root.expanduser().resolve()
    if not project_root.is_dir():
        logger.error(
            "--root must be an existing directory (got %s). "
            "re-run after fixing --root or delete out.json.",
            project_root,
        )
        return 1
    data_dir_arg = args.data.expanduser().resolve() if args.data is not None else None
    if data_dir_arg is not None and not data_dir_arg.is_dir():
        logger.error("--data must be an existing directory (got %s).", data_dir_arg)
        return 1

    save_queries_path = (
        _resolve_cli_path_before_chdir(args.save_queries)
        if args.save_queries is not None
        else None
    )
    output_csv_path = (
        _resolve_cli_path_before_chdir(args.output_csv)
        if args.output_csv is not None
        else None
    )

    pairs = load_questions(args.questions)
    rows_out: list[dict[str, Any]] = []
    contexts_per_row: list[list[str]] = []
    eval_samples: list[dict[str, Any]] = []

    for question, reference in pairs:
        logger.info("Querying GraphRAG: %s...", question[:80])
        try:
            answer, ctx = run_graphrag_query(
                project_root,
                data_dir_arg,
                args.method,
                question,
                community_level=args.community_level,
                dynamic_community_selection=args.dynamic_community_selection,
                response_type=args.response_type,
            )
            contexts = contexts_from_context_data(
                ctx,
                max_chunks=args.max_context_chunks,
            )
        except Exception:
            logger.exception("GraphRAG query failed")
            answer = ""
            contexts = ["(query failed — see logs)"]

        row = {
            "question": question,
            "answer": answer,
            "method": args.method,
            "context_count": len(contexts),
            "reference": reference,
        }
        rows_out.append(row)
        contexts_per_row.append(contexts)

        sample: dict[str, Any] = {
            "user_input": question,
            "response": answer,
            "retrieved_contexts": contexts,
        }
        if reference.strip():
            sample["reference"] = reference.strip()
        eval_samples.append(sample)

    if save_queries_path is not None:
        save_queries_path.parent.mkdir(parents=True, exist_ok=True)
        out_path = save_queries_path
        lim = max(0, args.save_query_snippet_chars)
        max_snips = max(0, args.save_query_max_context_snippets)
        disk_rows: list[dict[str, Any]] = []
        for r, ctxs in zip(rows_out, contexts_per_row, strict=True):
            snippets = [
                c[:lim] for c in ctxs[:max_snips] if isinstance(c, str) and c.strip()
            ]
            disk_rows.append({
                **r,
                "answer_chars": len(r.get("answer", "") or ""),
                "context_snippets": snippets,
            })
        payload = {
            "written_at": datetime.now(tz=UTC).isoformat(),
            "method": args.method,
            "root": str(project_root),
            "save_queries_path": str(out_path),
            "rows": disk_rows,
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Wrote query results to %s", out_path)

    if args.skip_eval:
        logger.info("Skipping Ragas (--skip-eval).")
        return 0

    if not eval_samples:
        logger.error("No samples to evaluate.")
        return 2

    logger.info("Running Ragas (Faithfulness + AnswerRelevancy)...")
    result = run_ragas(
        eval_samples,
        eval_model=args.eval_model,
        embedding_model=args.embedding_model,
        max_workers=args.max_workers,
    )
    logger.info("Ragas aggregate: %s", result)

    if output_csv_path is not None:
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        pdf = result.to_pandas()
        pdf.to_csv(output_csv_path, index=False, encoding="utf-8")
        logger.info("Wrote Ragas CSV to %s", output_csv_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

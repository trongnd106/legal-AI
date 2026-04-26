#!/usr/bin/env python3
"""Run GraphRAG indexing one file at a time.

Sau khi mỗi file được index xong, kết quả sẽ được đồng bộ vào Neo4j qua MERGE
(idempotent) để tích lũy graph dần theo thời gian.

Cấu hình Neo4j qua biến môi trường (hoặc args):
  NEO4J_URI       - ví dụ bolt://localhost:7687
  NEO4J_USERNAME  - mặc định: neo4j
  NEO4J_PASSWORD  - bắt buộc nếu dùng Neo4j
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

try:
    from neo4j import GraphDatabase as _GraphDatabase

    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False

if TYPE_CHECKING:
    from neo4j import Driver as Neo4jDriver


NEO4J_BATCH_SIZE = 500


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run GraphRAG index/update sequentially per text file."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/home/trong/Documents/graphrag"),
        help="Path to GraphRAG repository root.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path("/home/trong/graphrag_workspace"),
        help="Path to GraphRAG workspace root.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/home/trong/Documents/graphrag/data"),
        help="Directory containing .txt files to process.",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*",
        help="Glob pattern for source files.",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="standard",
        choices=["standard", "fast"],
        help="Indexing method for both initial index and update runs.",
    )
    parser.add_argument(
        "--keep-input-files",
        action="store_true",
        help="Keep files in workspace input folder after finishing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print planned commands without executing.",
    )

    # --- Neo4j ---
    neo4j_group = parser.add_argument_group("Neo4j sync")
    neo4j_group.add_argument(
        "--neo4j-uri",
        type=str,
        default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j Bolt URI (env: NEO4J_URI).",
    )
    neo4j_group.add_argument(
        "--neo4j-user",
        type=str,
        default=os.environ.get("NEO4J_USERNAME", "neo4j"),
        help="Neo4j username (env: NEO4J_USERNAME).",
    )
    neo4j_group.add_argument(
        "--neo4j-password",
        type=str,
        default=os.environ.get("NEO4J_PASSWORD", ""),
        help="Neo4j password (env: NEO4J_PASSWORD).",
    )
    neo4j_group.add_argument(
        "--no-neo4j",
        action="store_true",
        help="Tắt đồng bộ Neo4j, chỉ lưu parquet như cũ.",
    )
    return parser.parse_args()


def _is_supported_source(path: Path) -> bool:
    """Return True for supported document types."""
    if path.name.startswith(".~lock."):
        return False
    return path.suffix.lower() in {".txt", ".doc", ".docx"}


def _collect_source_files(source_dir: Path, pattern: str) -> list[Path]:
    """Collect and sort source files."""
    return sorted(
        p for p in source_dir.glob(pattern) if p.is_file() and _is_supported_source(p)
    )


def _convert_to_txt(source_file: Path, temp_dir: Path) -> Path:
    """Convert doc/docx to txt if needed and return text path."""
    if source_file.suffix.lower() == ".txt":
        return source_file

    temp_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "txt:Text",
        "--outdir",
        str(temp_dir),
        str(source_file),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Failed to convert {source_file.name} to txt.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    converted = temp_dir / f"{source_file.stem}.txt"
    if not converted.exists():
        raise FileNotFoundError(f"Converted file not found: {converted}")
    return converted


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------


def neo4j_connect(uri: str, user: str, password: str) -> Neo4jDriver:
    """Tạo và trả về Neo4j driver; raise nếu neo4j chưa được cài."""
    """Create and return a Neo4j driver; raise if neo4j is not installed."""
    if not _NEO4J_AVAILABLE:
        msg = "Package 'neo4j' chưa được cài. Chạy: uv add neo4j"
        raise ImportError(msg)
    return _GraphDatabase.driver(uri, auth=(user, password))


def neo4j_setup_constraints(driver: Neo4jDriver) -> None:
    """Create unique constraints for each node type (run once is enough)."""
    statements = [
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT text_unit_id IF NOT EXISTS FOR (n:TextUnit) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT community_id IF NOT EXISTS FOR (n:Community) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT community_report_id IF NOT EXISTS FOR (n:CommunityReport) REQUIRE n.id IS UNIQUE",
    ]
    with driver.session() as session:
        for stmt in statements:
            session.run(stmt)


def _neo4j_scalar(v: object) -> object:
    """Chuẩn hóa skalar / phần tử lặp: Neo4j chấp nhận primitive + None."""
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        x = float(v)
        if np.isnan(x) or np.isinf(x):
            return None
        return x
    if isinstance(v, str):
        return v
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def _value_has_nested_map(v: object) -> bool:
    """True nếu dict hoặc list/ndarray chứa dict (Neo4j không hỗ trợ map trong property)."""
    if isinstance(v, dict):
        return True
    if isinstance(v, (list, tuple)):
        return any(_value_has_nested_map(x) for x in v)
    if isinstance(v, np.ndarray) and v.size and v.dtype == object:
        return any(isinstance(x, dict) for x in v.ravel())
    return False


def _to_neo4j_property_value(v: object) -> object:
    """Một cell DataFrame/parquet -> giá trị hợp lệ trên thuộc tính Neo4j.

    dict, list[dict] (vd. cột *findings*), ndarray object chứa dict: lưu chuỗi JSON.
    list/tuple chỉ số/ký tự: giữ mảng primitive.
    """
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None

    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, default=str)

    if isinstance(v, (list, tuple)):
        if not v:
            return []
        if _value_has_nested_map(v):
            return json.dumps(list(v), ensure_ascii=False, default=str)
        return [_neo4j_scalar(x) for x in v]

    if isinstance(v, np.ndarray):
        if v.size == 0:
            return []
        if v.dtype == object and any(isinstance(x, dict) for x in v.ravel()):
            return json.dumps(v.tolist(), ensure_ascii=False, default=str)
        flat = v.tolist()
        if isinstance(flat, list) and _value_has_nested_map(flat):
            return json.dumps(flat, ensure_ascii=False, default=str)
        if isinstance(flat, list):
            return [_to_neo4j_property_value(x) for x in flat]
        return _to_neo4j_property_value(flat)

    return _neo4j_scalar(v)


def _df_to_rows(df: pd.DataFrame, extra: dict | None = None) -> list[dict]:
    """Chuyển DataFrame thành list[dict] an toàn cho Neo4j driver.

    - float NaN  -> None
    - numpy scalar -> Python primitive
    - list / ndarray -> primitive array or JSON string if nested map (e.g. findings)
    """
    result = []
    for row_dict in df.to_dict("records"):
        props: dict = {k: _to_neo4j_property_value(v) for k, v in row_dict.items()}
        if extra:
            props.update(extra)
        result.append(props)
    return result


def _batch_iter(rows: list, size: int = NEO4J_BATCH_SIZE):
    """Split list into smaller batches."""
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _merge_nodes(
    driver: Neo4jDriver,
    label: str,
    rows: list[dict],
    id_field: str = "id",
) -> None:
    """MERGE nodes by id_field, then SET all properties."""
    query = f"""
    UNWIND $rows AS row
    MERGE (n:{label} {{{id_field}: row.{id_field}}})
    SET n += row
    """
    with driver.session() as session:
        for batch in _batch_iter(rows):
            session.run(query, rows=batch)


def _merge_relationships(driver: Neo4jDriver, rows: list[dict]) -> None:
    """MERGE RELATED_TO relationships between Entities (lookup by title)."""
    query = """
    UNWIND $rows AS row
    MATCH (src:Entity {title: row.source})
    MATCH (tgt:Entity {title: row.target})
    MERGE (src)-[r:RELATED_TO {id: row.id}]->(tgt)
    SET r.human_readable_id = row.human_readable_id,
        r.description       = row.description,
        r.weight            = row.weight,
        r.combined_degree   = row.combined_degree,
        r.text_unit_ids     = row.text_unit_ids,
        r.source_file       = row.source_file
    """
    with driver.session() as session:
        for batch in _batch_iter(rows):
            session.run(query, rows=batch)


def neo4j_sync_dir(
    driver: Neo4jDriver,
    parquet_dir: Path,
    source_file: str,
) -> None:
    """Read all parquet files in parquet_dir and MERGE into Neo4j.

    Important order: Entity must be merged before Relationship.
    """
    extra = {"source_file": source_file}

    def _load(name: str) -> pd.DataFrame | None:
        path = parquet_dir / f"{name}.parquet"
        if not path.exists():
            return None
        return pd.read_parquet(path)

    tables: list[tuple[str, str]] = [
        ("documents", "Document"),
        ("text_units", "TextUnit"),
        ("entities", "Entity"),
        ("communities", "Community"),
        ("community_reports", "CommunityReport"),
    ]

    for table_name, label in tables:
        df = _load(table_name)
        if df is None or df.empty:
            continue
        rows = _df_to_rows(df, extra)
        _merge_nodes(driver, label, rows)
        print(f"  [Neo4j] MERGE {len(rows):>5} {label}")

    rel_df = _load("relationships")
    if rel_df is not None and not rel_df.empty:
        rows = _df_to_rows(rel_df, extra)
        _merge_relationships(driver, rows)
        print(f"  [Neo4j] MERGE {len(rows):>5} RELATED_TO")


def neo4j_sync_after_run(
    driver: Neo4jDriver,
    workspace_root: Path,
    source_file: str,
) -> None:
    """Sync current output (output/) into Neo4j after index/update.

    GraphRAG luôn hợp nhất kết quả mới vào output/ sau mỗi lần chạy,
    nên chỉ cần sync từ đây là đủ cho cả 'index' và 'update'.
    """
    output_dir = workspace_root / "output"
    if not output_dir.exists():
        print("  [Neo4j] Output/ not found, skipping sync.")
        return
    print(f"  [Neo4j] Syncing {output_dir} -> Neo4j ...")
    neo4j_sync_dir(driver, output_dir, source_file)


# ---------------------------------------------------------------------------


def ensure_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    """Validate and return required folders."""
    repo_root = args.repo_root.resolve()
    workspace_root = args.workspace_root.resolve()
    source_dir = args.source_dir.resolve()
    input_dir = workspace_root / "input"

    for path in (repo_root, workspace_root, source_dir):
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
    input_dir.mkdir(parents=True, exist_ok=True)
    return repo_root, workspace_root, source_dir, input_dir


def run_command(command: list[str], cwd: Path, dry_run: bool) -> int:
    """Execute command and return exit code."""
    print(f"$ {' '.join(command)}")
    if dry_run:
        return 0
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


def main() -> int:
    """Program entrypoint."""
    args = parse_args()
    repo_root, workspace_root, source_dir, input_dir = ensure_paths(args)

    files = sorted(source_dir.glob(args.pattern))
    files = _collect_source_files(source_dir, args.pattern)
    if not files:
        print(f"No files matched pattern '{args.pattern}' in {source_dir}")
        return 1

    # --- Khởi tạo Neo4j driver (nếu được bật) ---
    neo4j_driver: Neo4jDriver | None = None
    use_neo4j = not args.no_neo4j and not args.dry_run
    if use_neo4j:
        if not args.neo4j_password:
            print(
                "[Neo4j] Warning: NEO4J_PASSWORD is not set. "
                "Skip Neo4j sync (use --no-neo4j to disable this warning)."
            )
            use_neo4j = False
        else:
            try:
                neo4j_driver = neo4j_connect(
                    args.neo4j_uri, args.neo4j_user, args.neo4j_password
                )
                neo4j_driver.verify_connectivity()
                neo4j_setup_constraints(neo4j_driver)
                print(
                    f"[Neo4j] Connected: {args.neo4j_uri} "
                    f"(user={args.neo4j_user})"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[Neo4j] Cannot connect: {exc}")
                print("[Neo4j] Continue with parquet only.")
                neo4j_driver = None
                use_neo4j = False

    output_dir = workspace_root / "output"
    temp_dir = workspace_root / ".tmp_per_file_index"
    runs_ok = True

    original_input_files = list(input_dir.glob("*"))

    for idx, source_file in enumerate(files):
        if not source_file.is_file():
            continue

        print(f"\n=== Processing {source_file.name} ({idx + 1}/{len(files)}) ===")

        for old in input_dir.glob("*"):
            if old.is_file():
                old.unlink()

        prepared_file = _convert_to_txt(source_file, temp_dir)
        target_file = input_dir / prepared_file.name
        if not args.dry_run:
            shutil.copy2(prepared_file, target_file)

        has_existing_output = output_dir.exists() and any(output_dir.glob("*.parquet"))
        # Existing index result (even new run) → update; no output → first index
        command_name = "update" if has_existing_output else "index"
        command = [
            "uv",
            "run",
            "poe",
            command_name,
            "--root",
            str(workspace_root),
            "--method",
            args.method,
            "--verbose",
        ]

        exit_code = run_command(command, cwd=repo_root, dry_run=args.dry_run)
        print(f"exit={exit_code}")
        if exit_code != 0:
            runs_ok = False

        # --- Sync result to Neo4j ---
        if use_neo4j and neo4j_driver and exit_code == 0:
            try:
                neo4j_sync_after_run(neo4j_driver, workspace_root, source_file.name)
            except Exception as exc:  # noqa: BLE001
                print(f"  [Neo4j] Error syncing: {exc}")

        if not runs_ok:
            print("Stopping due to non-zero exit code (exit_code != 0).")
            break

    if not args.keep_input_files:
        for old in input_dir.glob("*"):
            if old.is_file():
                old.unlink()
        for old in original_input_files:
            if old.is_file():
                shutil.copy2(old, input_dir / old.name)
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    if neo4j_driver:
        neo4j_driver.close()

    return 0 if runs_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

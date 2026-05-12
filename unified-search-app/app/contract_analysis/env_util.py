# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Tải biến môi trường `.env` (Neo4j, API...) từ repo hoặc cwd."""

from __future__ import annotations

from pathlib import Path


def load_repo_dotenv() -> None:
    """Gọi ``python-dotenv`` trên file `.env` đầu tiên tìm thấy (cwd → cha của app)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    seen: set[Path] = set()
    candidates: list[Path] = [Path.cwd()]
    here = Path(__file__).resolve()
    for i in range(min(6, len(here.parents))):
        candidates.append(here.parents[i])

    for base in candidates:
        env_path = (base / ".env").resolve()
        if env_path in seen:
            continue
        seen.add(env_path)
        if env_path.is_file():
            load_dotenv(env_path)
            return

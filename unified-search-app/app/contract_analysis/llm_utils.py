# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Khởi tạo LLM từ GraphRagConfig và parse JSON an toàn."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from graphrag_llm.completion import create_completion

if TYPE_CHECKING:
    from graphrag.config.models.graph_rag_config import GraphRagConfig
    from graphrag_llm.completion.completion import LLMCompletion


def get_completion_for_contract_tasks(config: "GraphRagConfig") -> "LLMCompletion":
    """Dùng cùng completion model với basic_search để đồng bộ chi phí / quota."""
    model_id = config.basic_search.completion_model_id
    model_settings = config.get_completion_model_config(model_id)
    return create_completion(model_settings)


async def llm_chat_json(llm: "LLMCompletion", system: str, user: str) -> Any:
    """Gọi LLM và parse JSON (array hoặc object)."""
    resp = await llm.completion_async(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_completion_tokens=8192,
    )
    text = resp.content.strip()
    # Loại bỏ fence ```json ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        from json_repair import repair_json

        repaired = repair_json(text)
        return json.loads(repaired)

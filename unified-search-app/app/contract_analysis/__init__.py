# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Phân tích hợp đồng lao động — pipeline tích hợp GraphRAG (không ghi vào Neo4j).

Phiên bản này map điều khoản sang ngữ cảnh pháp luật qua ``basic_search`` trên
text_units của dataset đã index (ví dụ văn bản BLLĐ, NĐ trong GraphRAG).
"""

from contract_analysis.pipeline import run_contract_analysis

__all__ = ["run_contract_analysis"]

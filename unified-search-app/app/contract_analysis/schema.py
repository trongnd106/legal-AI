# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Pydantic models cho pipeline phân tích HĐLĐ."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ExtractionMethod = Literal[
    "pdfplumber",
    "paddleocr",
    "docx",
    "txt",
    "plain_upload",
]


class ContractMetadata(BaseModel):
    """Siêu dữ liệu file hợp đồng."""

    filename: str = ""
    total_pages: int | None = None
    detected_language: str = "vi"
    contract_type: Literal["labor", "unknown"] = "unknown"
    labor_keyword_score: float = Field(ge=0.0, le=1.0, default=0.0)
    extraction_method: ExtractionMethod = "txt"


class ContractDocument(BaseModel):
    """Văn bản HĐ sau khi load."""

    raw_text: str
    pages: list[dict[str, str | int]] = Field(default_factory=list)
    metadata: ContractMetadata = Field(default_factory=ContractMetadata)


class Clause(BaseModel):
    """Một điều khoản đã tách."""

    clause_id: str
    title: str = ""
    category: str = "UNKNOWN"
    categories: list[str] = Field(default_factory=list)
    original_text: str = ""
    summary: str = ""
    article_number: str | None = None

    def effective_categories(self) -> set[str]:
        """Tập category áp dụng cho điều khoản (gồm cả ``category`` và ``categories``)."""
        out = {c.upper() for c in self.categories if c}
        if self.category:
            out.add(self.category.upper())
        return out


class MappedLawSnippet(BaseModel):
    """Kết quả rút gọn từ GraphRAG basic_search cho một điều khoản."""

    query_used: str = ""
    rag_answer: str = ""
    relevance_note: str = "semantic_chunks"


class ClauseAnalysis(BaseModel):
    """Phân tích một điều khoản."""

    clause: Clause
    mapped_laws: MappedLawSnippet | None = None
    rule_issues: list["ContractIssue"] = Field(default_factory=list)
    llm_issues: list["ContractIssue"] = Field(default_factory=list)


Severity = Literal[
    "VIOLATION",
    "HIGH_RISK",
    "MEDIUM_RISK",
    "COMPLIANT",
    "NOT_COVERED",
]


class ContractIssue(BaseModel):
    """Một vấn đề / rủi ro."""

    issue_id: str
    description: str
    severity: Severity
    legal_basis: str = ""
    recommendation: str = ""
    affected_party: str = ""
    clause_id: str | None = None


class ContractAnalysisResult(BaseModel):
    """Toàn bộ kết quả."""

    contract: ContractDocument
    clauses: list[Clause] = Field(default_factory=list)
    missing_mandatory: list[str] = Field(default_factory=list)
    per_clause: list[ClauseAnalysis] = Field(default_factory=list)
    compliance_score: float = 100.0
    markdown_report: str = ""
    analysis_session_id: str | None = None

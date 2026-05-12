# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Unit tests cho rule-based detector và điểm tuân thủ."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Cho phép `python -m unittest` từ thư mục unified-search-app
_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from contract_analysis.reporter import finalize_report
from contract_analysis.rules import RuleContext, apply_rules
from contract_analysis.schema import (
    Clause,
    ClauseAnalysis,
    ContractAnalysisResult,
    ContractDocument,
    ContractIssue,
    ContractMetadata,
)
from contract_analysis.segmenter import compute_missing_mandatory, infer_categories_from_text


class RuleTests(unittest.TestCase):
    def test_salary_below_minimum_violation(self):
        c = Clause(
            clause_id="c1",
            category="SALARY",
            original_text="Mức lương: 2.000.000 đồng/tháng.",
            summary="Lương 2 triệu",
        )
        issues = apply_rules(c, RuleContext(region="IV"))
        self.assertTrue(any(i.issue_id == "VR001" for i in issues))

    def test_weekly_hours_over_48(self):
        c = Clause(
            clause_id="c2",
            category="WORKING_HOURS",
            original_text="Thời giờ làm việc 52 giờ/tuần.",
            summary="52h/tuần",
        )
        issues = apply_rules(c, RuleContext())
        self.assertTrue(any(i.issue_id == "VR003" for i in issues))


class MissingMandatoryTests(unittest.TestCase):
    def test_multi_category_clause_not_reported_missing(self):
        c = Clause(
            clause_id="c1",
            category="JOB_DESCRIPTION",
            categories=["JOB_DESCRIPTION", "WORKPLACE", "CONTRACT_TYPE", "CONTRACT_DURATION"],
            original_text="Công việc, địa điểm làm việc và thời hạn của Hợp đồng",
            summary="",
        )
        missing = compute_missing_mandatory([c])
        for k in ("JOB_DESCRIPTION", "WORKPLACE", "CONTRACT_TYPE", "CONTRACT_DURATION"):
            self.assertNotIn(k, missing)

    def test_raw_text_backfill(self):
        c = Clause(
            clause_id="c1",
            category="JOB_DESCRIPTION",
            categories=["JOB_DESCRIPTION"],
            original_text="",
            summary="",
        )
        raw = (
            "Điều 1: Công việc, địa điểm làm việc và thời hạn của Hợp đồng\n"
            "- Công việc phải làm: Nhân viên Marketing\n"
            "- Địa điểm làm việc: Số 188 Trung Kính, Cầu Giấy, Hà Nội\n"
            "Loại hợp đồng: Hợp đồng xác định thời hạn – Ký lần thứ nhất\n"
            "Từ ngày: 25/08/2025 Đến ngày: 25/08/2027\n"
        )
        missing = compute_missing_mandatory([c], raw_text=raw)
        for k in ("WORKPLACE", "CONTRACT_TYPE", "CONTRACT_DURATION", "JOB_DESCRIPTION"):
            self.assertNotIn(k, missing)

    def test_heuristic_detects_known_categories(self):
        found = infer_categories_from_text(
            "địa điểm làm việc: Hà Nội. Mức lương 7.000.000 đồng/tháng. BHXH 8%.",
        )
        self.assertIn("WORKPLACE", found)
        self.assertIn("SALARY", found)
        self.assertIn("SOCIAL_INSURANCE", found)


class ScoreTests(unittest.TestCase):
    def test_compliance_penalties(self):
        doc = ContractDocument(raw_text="x", metadata=ContractMetadata(filename="t.txt"))
        cl = Clause(clause_id="x", category="SALARY", original_text="", summary="")
        analysis = ContractAnalysisResult(
            contract=doc,
            clauses=[cl],
            missing_mandatory=["SALARY"],
            per_clause=[
                ClauseAnalysis(
                    clause=cl,
                    rule_issues=[
                        ContractIssue(
                            issue_id="VR001",
                            description="low pay",
                            severity="VIOLATION",
                        ),
                    ],
                    llm_issues=[],
                ),
            ],
        )
        finalize_report(analysis)
        self.assertLess(analysis.compliance_score, 100.0)
        self.assertIn("VR001", analysis.markdown_report)

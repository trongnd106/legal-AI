# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Test seed entity cho Neo4j KG."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

import pandas as pd

from contract_analysis.entity_seed import seed_entity_ids_for_clause
from contract_analysis.schema import Clause


class EntitySeedTests(unittest.TestCase):
    def test_salary_clause_hits_luong_entity(self):
        entities = pd.DataFrame([
            {"id": "e1", "title": "Tiền lương", "description": "Thù lao hàng tháng", "degree": 2},
            {"id": "e2", "title": "XE BUYT", "description": "Phương tiện", "degree": 1},
        ])
        rel = pd.DataFrame([
            {"source": "Tiền lương", "target": "XE BUYT", "description": "Không liên quan lương"},
        ])
        c = Clause(
            clause_id="c1",
            category="SALARY",
            title="Điều lương",
            summary="Mức lương cơ bản 10 triệu",
            original_text="",
        )
        ids = seed_entity_ids_for_clause(c, entities, relationships_df=rel, top_k=5)
        self.assertIn("e1", ids)
        self.assertEqual(ids[0], "e1")


if __name__ == "__main__":
    unittest.main()

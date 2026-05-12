# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Ghi phiên phân tích HĐLĐ lên Neo4j (ContractSession / ContractClause / ContractIssue)."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from contract_analysis.env_util import load_repo_dotenv

if TYPE_CHECKING:
    from neo4j import Driver

    from contract_analysis.schema import ContractAnalysisResult

logger = logging.getLogger(__name__)

_MAX_PROP = 120_000


def _sanitize(s: str) -> str:
    if len(s) <= _MAX_PROP:
        return s
    return s[: _MAX_PROP - 20] + "\n...[truncated]..."


def get_driver_from_env() -> Driver | None:
    """Trả driver nếu có ``NEO4J_URI`` và ``NEO4J_PASSWORD``."""
    import os

    load_repo_dotenv()
    uri = (os.environ.get("NEO4J_URI") or "").strip()
    user = (os.environ.get("NEO4J_USERNAME") or "neo4j").strip()
    pwd = (os.environ.get("NEO4J_PASSWORD") or "").strip()
    if not uri or not pwd:
        return None
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.warning("Package neo4j chưa cài.")
        return None
    return GraphDatabase.driver(uri, auth=(user, pwd))


def setup_contract_constraints(driver: Driver) -> None:
    """Ràng buộc / index cho subgraph phân tích HĐ."""
    stmts = [
        "CREATE CONSTRAINT contract_session_id_unique IF NOT EXISTS "
        "FOR (s:ContractSession) REQUIRE s.session_id IS UNIQUE",
        "CREATE CONSTRAINT contract_clause_uid_unique IF NOT EXISTS "
        "FOR (c:ContractClause) REQUIRE c.uid IS UNIQUE",
        "CREATE CONSTRAINT contract_issue_uid_unique IF NOT EXISTS "
        "FOR (i:ContractIssue) REQUIRE i.uid IS UNIQUE",
        "CREATE INDEX contract_clause_session IF NOT EXISTS "
        "FOR (c:ContractClause) ON (c.session_id)",
        "CREATE INDEX contract_clause_category IF NOT EXISTS "
        "FOR (c:ContractClause) ON (c.category)",
    ]
    with driver.session() as session:
        for q in stmts:
            try:
                session.run(q)
            except Exception as e:
                logger.debug("Neo4j constraint/index (có thể đã tồn tại): %s", e)


def _clause_severity(ca: Any) -> str:
    sevs = [i.severity for i in ca.rule_issues + ca.llm_issues]
    order = ["VIOLATION", "HIGH_RISK", "MEDIUM_RISK", "COMPLIANT", "NOT_COVERED"]
    for s in order:
        if s in sevs:
            return s
    return "NOT_COVERED"


def persist_contract_analysis(result: ContractAnalysisResult) -> bool:
    """
    MERGE ``ContractSession`` và các node con. ``analysis_session_id`` bắt buộc.

    Returns
    -------
    bool
        True nếu ghi Neo4j thành công.
    """
    sid = result.analysis_session_id
    if not sid:
        return False

    driver = get_driver_from_env()
    if driver is None:
        logger.info("Bỏ qua Neo4j: thiếu NEO4J_URI hoặc NEO4J_PASSWORD.")
        return False

    meta = result.contract.metadata
    fn = _sanitize(meta.filename or "unknown")

    def safe_key(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.:-]+", "_", s)[:200]

    try:
        setup_contract_constraints(driver)
        with driver.session() as session:
            session.run(
                """
                MERGE (s:ContractSession {session_id: $sid})
                SET s.contract_filename = $fn,
                    s.compliance_score = $score,
                    s.extraction_method = $ext,
                    s.detected_contract_type = $ctype,
                    s.labor_keyword_score = $lk,
                    s.updated_at = datetime()
                """,
                sid=sid,
                fn=fn,
                score=float(result.compliance_score),
                ext=meta.extraction_method,
                ctype=meta.contract_type,
                lk=float(meta.labor_keyword_score),
            )

            for ca in result.per_clause:
                c = ca.clause
                uid = f"{sid}:{safe_key(c.clause_id)}"
                sev = _clause_severity(ca)
                session.run(
                    """
                    MATCH (s:ContractSession {session_id: $sid})
                    MERGE (cl:ContractClause {uid: $uid})
                    SET cl.session_id = $sid,
                        cl.clause_id = $clause_id,
                        cl.category = $cat,
                        cl.title = $title,
                        cl.summary = $summary,
                        cl.original_text = $otext,
                        cl.severity = $sev,
                        cl.article_number = $art
                    MERGE (s)-[:CONTAINS_CLAUSE]->(cl)
                    """,
                    sid=sid,
                    uid=uid,
                    clause_id=c.clause_id,
                    cat=_sanitize(c.category or ""),
                    title=_sanitize(c.title or ""),
                    summary=_sanitize(c.summary or ""),
                    otext=_sanitize(c.original_text or ""),
                    sev=sev,
                    art=c.article_number or "",
                )

                for iss in ca.rule_issues + ca.llm_issues:
                    i_uid = f"{sid}:{safe_key(iss.issue_id)}:{safe_key(c.clause_id)}"
                    session.run(
                        """
                        MATCH (cl:ContractClause {uid: $c_uid})
                        MERGE (i:ContractIssue {uid: $i_uid})
                        SET i.issue_id = $issue_id,
                            i.description = $desc,
                            i.severity = $sev,
                            i.legal_basis = $lb,
                            i.recommendation = $rec,
                            i.affected_party = $ap,
                            i.session_id = $sid
                        MERGE (cl)-[:HAS_ISSUE]->(i)
                        """,
                        c_uid=uid,
                        i_uid=i_uid,
                        issue_id=iss.issue_id,
                        desc=_sanitize(iss.description),
                        sev=iss.severity,
                        lb=_sanitize(iss.legal_basis),
                        rec=_sanitize(iss.recommendation),
                        ap=_sanitize(iss.affected_party),
                        sid=sid,
                    )

        logger.info("Đã ghi Neo4j ContractSession %s", sid)
        return True
    except Exception:
        logger.exception("Lỗi ghi Neo4j cho phiên %s", sid)
        return False
    finally:
        driver.close()


def neo4j_configured() -> bool:
    import os

    load_repo_dotenv()
    return bool((os.environ.get("NEO4J_URI") or "").strip() and (os.environ.get("NEO4J_PASSWORD") or "").strip())

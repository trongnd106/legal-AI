#!/usr/bin/env python3
"""Run RAGAS Faithfulness + AnswerRelevancy on pre-computed results from results/."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import types
from pathlib import Path

# Monkeypatch missing vertexai import in ragas 0.4.3
# (we don't use VertexAI — this just bypasses ragas' broken import chain)
_vertexai_dummy = types.ModuleType("langchain_community.chat_models.vertexai")

class _FakeChatVertexAI:
    pass

_vertexai_dummy.ChatVertexAI = _FakeChatVertexAI
sys.modules["langchain_community.chat_models.vertexai"] = _vertexai_dummy

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
AVAILABLE_FILES = {
    "zero-shot": "ragas_input_zero-shot_llm.json",
    "basic": "ragas_input_basic_search.json",
    "local": "ragas_input_local_search.json",
    "global": "ragas_input_global_search.json",
    "multihop": "ragas_input_local_multihop.json",
}

# ── Vietnamese prompts for RAGAS ──────────────────────────────────────────
# These override the default English prompts with Vietnamese legal-domain text.

VI_STATEMENT_GENERATOR_INSTRUCTION = """Cho một câu hỏi và một câu trả lời, hãy phân tích độ phức tạp trong từng câu của câu trả lời. Phân tích mỗi câu thành một hoặc nhiều nhận định (statement) hoàn chỉnh, dễ hiểu. Đảm bảo không sử dụng đại từ (như "ông", "bà", "anh", "chị", "nó", "họ") trong bất kỳ nhận định nào — thay thế bằng danh từ cụ thể."""

VI_STATEMENT_GENERATOR_EXAMPLES = [
    (
        {
            "question": "Người lao động làm việc theo hợp đồng lao động có thời hạn 12 tháng có được hưởng trợ cấp thôi việc không?",
            "answer": "Theo Điều 46 BLLĐ 2019, người lao động làm việc từ đủ 12 tháng trở lên khi chấm dứt hợp đồng lao động theo quy định tại các điều 34, 35, 36, 37, 39, 40 và 41 của Bộ luật này thì được hưởng trợ cấp thôi việc. Như vậy, người lao động có hợp đồng 12 tháng đủ điều kiện hưởng trợ cấp thôi việc nếu đáp ứng các điều kiện luật định.",
        },
        {
            "statements": [
                "Điều 46 BLLĐ 2019 quy định về trợ cấp thôi việc.",
                "Người lao động làm việc từ đủ 12 tháng trở lên được hưởng trợ cấp thôi việc.",
                "Trợ cấp thôi việc được áp dụng khi chấm dứt hợp đồng lao động theo các điều 34, 35, 36, 37, 39, 40 và 41.",
                "Người lao động có hợp đồng 12 tháng có thể đủ điều kiện hưởng trợ cấp thôi việc.",
            ]
        },
    )
]

VI_NLI_INSTRUCTION = """Nhiệm vụ của bạn là đánh giá tính trung thực (faithfulness) của một loạt nhận định dựa trên ngữ cảnh được cung cấp. Với mỗi nhận định, trả về kết quả là 1 nếu nhận định có thể suy luận trực tiếp từ ngữ cảnh, hoặc 0 nếu nhận định không thể suy luận trực tiếp từ ngữ cảnh."""

VI_NLI_EXAMPLES = [
    (
        {
            "context": "Điều 46 BLLĐ 2019 quy định về trợ cấp thôi việc. Người lao động làm việc từ đủ 12 tháng trở lên khi chấm dứt hợp đồng lao động theo quy định tại các điều 34, 35, 36, 37, 39, 40 và 41 thì được hưởng trợ cấp thôi việc.",
            "statements": [
                "Điều 46 BLLĐ 2019 quy định về trợ cấp thôi việc.",
                "Người lao động làm việc dưới 6 tháng được hưởng trợ cấp thôi việc.",
                "Trợ cấp thôi việc áp dụng khi chấm dứt hợp đồng theo các điều luật quy định.",
            ],
        },
        {
            "statements": [
                {
                    "statement": "Điều 46 BLLĐ 2019 quy định về trợ cấp thôi việc.",
                    "reason": "Ngữ cảnh trực tiếp nêu 'Điều 46 BLLĐ 2019 quy định về trợ cấp thôi việc.'",
                    "verdict": 1,
                },
                {
                    "statement": "Người lao động làm việc dưới 6 tháng được hưởng trợ cấp thôi việc.",
                    "reason": "Ngữ cảnh yêu cầu làm việc từ đủ 12 tháng trở lên, không phải dưới 6 tháng.",
                    "verdict": 0,
                },
                {
                    "statement": "Trợ cấp thôi việc áp dụng khi chấm dứt hợp đồng theo các điều luật quy định.",
                    "reason": "Ngữ cảnh nêu rõ trợ cấp thôi việc áp dụng khi chấm dứt hợp đồng theo các điều 34, 35, 36, 37, 39, 40 và 41.",
                    "verdict": 1,
                },
            ]
        },
    )
]

VI_ANSWER_RELEVANCY_INSTRUCTION = """Tạo một câu hỏi cho câu trả lời được cung cấp và xác định xem câu trả lời có mang tính né tránh (noncommittal) hay không.
Trả về noncommittal = 1 nếu câu trả lời mang tính né tránh, mơ hồ, hoặc không rõ ràng; và noncommittal = 0 nếu câu trả lời có nội dung cụ thể, rõ ràng.
Ví dụ câu trả lời né tránh: "Tôi không biết", "Tôi không chắc", "Còn tùy thuộc"."""

VI_ANSWER_RELEVANCY_EXAMPLES = [
    (
        {"response": "Mức lương tối thiểu vùng I là 4.960.000 đồng/tháng theo Nghị định 38/2022/NĐ-CP."},
        {"question": "Mức lương tối thiểu vùng I là bao nhiêu?", "noncommittal": 0},
    ),
    (
        {"response": "Tôi không có đủ thông tin để trả lời câu hỏi này."},
        {"question": "Mức lương tối thiểu vùng I là bao nhiêu?", "noncommittal": 1},
    ),
]

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_vi_faithfulness(llm):
    """Create Faithfulness metric with Vietnamese prompts (old-style API)."""
    from ragas.metrics._faithfulness import (
        Faithfulness as OldFaithfulness,
        NLIStatementPrompt,
        StatementGeneratorPrompt,
    )
    from ragas.metrics._faithfulness import (
        StatementGeneratorInput,
        StatementGeneratorOutput,
        NLIStatementInput,
        NLIStatementOutput,
        StatementFaithfulnessAnswer,
    )

    class ViStatementGeneratorPrompt(StatementGeneratorPrompt):
        instruction = VI_STATEMENT_GENERATOR_INSTRUCTION
        examples = [
            (
                StatementGeneratorInput(**ex[0]),
                StatementGeneratorOutput(**ex[1]),
            )
            for ex in VI_STATEMENT_GENERATOR_EXAMPLES
        ]

    class ViNLIStatementPrompt(NLIStatementPrompt):
        instruction = VI_NLI_INSTRUCTION
        examples = [
            (
                NLIStatementInput(**ex_in),
                NLIStatementOutput(
                    statements=[
                        StatementFaithfulnessAnswer(**s)
                        for s in ex_out["statements"]
                    ]
                ),
            )
            for ex_in, ex_out in VI_NLI_EXAMPLES
        ]

    metric = OldFaithfulness(llm=llm)
    metric.set_prompts(
        statement_generator_prompt=ViStatementGeneratorPrompt(),
        n_l_i_statement_prompt=ViNLIStatementPrompt(),
    )
    return metric


def _make_vi_answer_relevancy(llm, embeddings):
    """Create AnswerRelevancy metric with Vietnamese prompts (old-style API)."""
    from ragas.metrics._answer_relevance import (
        AnswerRelevancy as OldAnswerRelevancy,
        ResponseRelevancePrompt,
        ResponseRelevanceInput,
        ResponseRelevanceOutput,
    )

    class ViResponseRelevancePrompt(ResponseRelevancePrompt):
        name = "response_relevance_prompt"
        instruction = VI_ANSWER_RELEVANCY_INSTRUCTION
        examples = [
            (
                ResponseRelevanceInput(**ex[0]),
                ResponseRelevanceOutput(**ex[1]),
            )
            for ex in VI_ANSWER_RELEVANCY_EXAMPLES
        ]

    metric = OldAnswerRelevancy(llm=llm, embeddings=embeddings)
    metric.set_prompts(response_relevance_prompt=ViResponseRelevancePrompt())
    return metric


# ── RAGAS runner ───────────────────────────────────────────────────────────


def run_ragas(
    samples: list[dict],
    *,
    eval_model: str,
    embedding_model: str,
    max_workers: int,
    skip_faithfulness: bool = False,
    vietnamese: bool = True,
):
    from openai import OpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import llm_factory
    from ragas.run_config import RunConfig

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required. Set it in the environment.")

    openai_client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    evaluator_llm = llm_factory(
        eval_model,
        provider="openai",
        client=openai_client,
        temperature=0.1,
        max_tokens=2048,
    )

    from langchain_openai import OpenAIEmbeddings as LangChainOpenAIEmbeddings

    lc_embeddings = LangChainOpenAIEmbeddings(
        openai_api_key=api_key,
        model=embedding_model,
        openai_api_base="https://openrouter.ai/api/v1",
    )

    metrics = []
    if vietnamese:
        if not skip_faithfulness:
            metrics.append(_make_vi_faithfulness(evaluator_llm))
        metrics.append(_make_vi_answer_relevancy(evaluator_llm, lc_embeddings))
    else:
        from ragas.metrics._faithfulness import Faithfulness as OldFaithfulness
        from ragas.metrics._answer_relevance import AnswerRelevancy as OldAnswerRelevancy

        if not skip_faithfulness:
            metrics.append(OldFaithfulness(llm=evaluator_llm))
        metrics.append(OldAnswerRelevancy(llm=evaluator_llm, embeddings=lc_embeddings))

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
        metrics=metrics,
        llm=evaluator_llm,
        embeddings=None,
        run_config=rc,
        show_progress=True,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--methods",
        nargs="+",
        choices=list(AVAILABLE_FILES) + ["all"],
        default=["local"],
        help="Methods to evaluate (default: local).",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_DIR,
    )
    p.add_argument(
        "--max-context-chunks",
        type=int,
        default=20,
    )
    p.add_argument(
        "--eval-model",
        default="openai/gpt-4o-mini",
    )
    p.add_argument(
        "--embedding-model",
        default="openai/text-embedding-3-small",
    )
    p.add_argument(
        "--max-workers",
        type=int,
        default=2,
    )
    p.add_argument(
        "--skip-faithfulness",
        action="store_true",
    )
    p.add_argument(
        "--no-vi",
        action="store_true",
        help="Use default English RAGAS prompts instead of Vietnamese.",
    )
    args = p.parse_args(argv)

    methods = list(AVAILABLE_FILES) if "all" in args.methods else args.methods

    for method in methods:
        file_path = RESULTS_DIR / AVAILABLE_FILES[method]
        if not file_path.exists():
            logger.warning("File not found: %s — skipping %s", file_path, method)
            continue

        logger.info("Loading %s (%s)...", file_path, method)
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        logger.info("  %d samples loaded.", len(raw))

        samples = []
        for r in raw:
            ctxs = r.get("contexts") or []
            if args.max_context_chunks > 0:
                ctxs = ctxs[: args.max_context_chunks]
            sample = {
                "user_input": r["question"],
                "response": r["answer"],
                "retrieved_contexts": ctxs,
            }
            ref = r.get("reference") or ""
            if ref.strip():
                sample["reference"] = ref.strip()
            samples.append(sample)

        skip_faith = args.skip_faithfulness or method == "zero-shot"
        logger.info("Running RAGAS on %s (Faithfulness=%s, Vietnamese=%s)...", method, not skip_faith, not args.no_vi)
        result = run_ragas(
            samples,
            eval_model=args.eval_model,
            embedding_model=args.embedding_model,
            max_workers=args.max_workers,
            skip_faithfulness=skip_faith,
            vietnamese=not args.no_vi,
        )

        print(f"\n=== {method.upper()} ===")
        print(result)

        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"ragas_scores_{method}.csv"
        pdf = result.to_pandas()
        pdf.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info("Saved per-row scores to %s", csv_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

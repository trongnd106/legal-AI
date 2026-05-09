# Benchmark GraphRAG - RAGAS

> Tối ưu cho Gemini Free Tier — không cần OpenAI API key làm evaluator

Tài liệu này gắn với codebase **microsoft/graphrag** trong repo hiện tại: CLI `graphrag`, package Python `packages/graphrag` (xem phiên bản trong `packages/graphrag/pyproject.toml`). Tham khảo thêm [docs chính thức](https://microsoft.github.io/graphrag/get_started/).

---

## Tổng quan

RAGAS (RAG Assessment) dùng **LLM-as-a-Judge**: một LLM chấm output của pipeline GraphRAG. Với setup Gemini Flash làm evaluator, chi phí có thể thấp hoặc nằm trong free tier (tùy hạn mức Google AI Studio).

### Luồng hoạt động

```
Câu hỏi → GraphRAG query (global / local / drift / basic) → [Answer + Contexts cho RAGAS]
                                                                    ↓
                                                    RAGAS (Gemini làm Judge)
                                                                    ↓
                                    Điểm số: Faithfulness, Response Relevancy, ...
```

---

## Phần 0 — Bối cảnh dự án & cách chạy GraphRAG

- **Phiên bản Python**: ≥ 3.11, < 3.14 (theo `packages/graphrag/pyproject.toml`).
- **Cài đặt từ PyPI** (người dùng cuối): `pip install graphrag` hoặc công cụ tương đương; entrypoint là lệnh `graphrag`.
- **Phát triển trong monorepo này**:
  ```bash
  cd /path/to/graphrag   # thư mục gốc workspace
  uv sync
  uv run poe query -- --help    # ví dụ: bọc argument sau `--`
  # hoặc: uv run python -m graphrag query --help
  ```
- **Khởi tạo & index một project**: `graphrag init --root <thư_mục_project>` rồi `graphrag index --root <thư_mục_project>` — xem README repo và [CLI quickstart](https://microsoft.github.io/graphrag/get_started/). Giữa các bản minor nên chạy lại `graphrag init --root ... --force` khi đổi format config (ghi chú trong `README.md` gốc).

**Output index**: Mặc định các bảng nằm dưới thư mục do `output_storage.base_dir` trong `settings.yaml` quyết định — thường là `./output` so với `--root`. Nếu index nằm chỗ khác, CLI hỗ trợ `--data` / `-d` trỏ thẳng vào thư mục đó.

---

## Phần 1 — Cài RAGAS (môi trường benchmark)

```bash
pip install ragas langchain-google-genai datasets pandas
```

Kiểm tra phiên bản Ragas:

```bash
pip show ragas  # khuyến nghị theo changelog Ragas của bạn, thường >= 0.2.x
```

---

## Phần 2 — Cấu hình Gemini làm Evaluator LLM

Ragas thường bọc Gemini qua LangChain (`LangchainLLMWrapper`, `LangchainEmbeddingsWrapper`).

```python
import os
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

os.environ["GOOGLE_API_KEY"] = "YOUR_GEMINI_API_KEY"  # hoặc `.env`

evaluator_llm = LangchainLLMWrapper(
    ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        max_tokens=2048,
    )
)

evaluator_embeddings = LangchainEmbeddingsWrapper(
    GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        task_type="retrieval_document",
    )
)
```

Nếu gặp lỗi Pydantic / structured output không ổn định với Gemini 2.x, thử đổi model sang bản Flash ổn định hơn theo khuyến cáo Ragas/Google tại thời điểm bạn chạy.

---

## Phần 3 — Chạy query GraphRAG & lấy câu trả lời

### 3.1 CLI (nhanh, chỉ có chuỗi trả lời in ra stdout)

Trong codebase này, `SearchMethod` hỗ trợ các giá trị (chữ thường): `**global**`, `**local**`, `**drift**`, `**basic**` — xem `packages/graphrag/graphrag/config/enums.py`.

Ví dụ:

```bash
graphrag query "Các chủ đề chính trong tài liệu là gì?" \
  --root /path/to/my_graphrag_project \
  --method global \
  --response-type "Multiple Paragraphs"
```

Tùy chọn thường dùng khi benchmark:


| Tham số                                                    | Ý nghĩa                                                    |
| ---------------------------------------------------------- | ---------------------------------------------------------- |
| `--root`, `-r`                                             | Thư mục project (có `settings.yaml`).                      |
| `--method`, `-m`                                           | `global` / `local` / `drift` / `basic`.                    |
| `--data`, `-d`                                             | Thư mục output index (override `output_storage.base_dir`). |
| `--community-level`                                        | Cấp community (global/local/drift); mặc định CLI là `2`.   |
| `--dynamic-community-selection` / `--no-dynamic-selection` | Cho global search.                                         |
| `--response-type`                                          | Mô tả format câu trả lời (mặc định `Multiple Paragraphs`). |


**Hạn chế**: CLI chỉ in phần trả lời; không xuất sẵn danh sách context đã đưa vào prompt. Với Faithfulness, nên dùng **API Python** bên dưới để lấy `context_data`, hoặc fallback đọc artifact (Phần 4).

### 3.2 API Python (khuyến nghị cho RAGAS) — `context_data` thật

`graphrag.api.global_search` / `local_search` trả về `(response, context_data)`. Bạn có thể chuyển các `DataFrame` trong `context_data` thành chuỗi (hoặc dùng `graphrag.utils.api.reformat_context_data` nếu muốn dạng record JSON).

Ví dụ tối giản **global search** (pattern giống `packages/graphrag/graphrag/cli/query.py`):

```python
import asyncio
from pathlib import Path

import graphrag.api as api
from graphrag.config.load_config import load_config
from graphrag.data_model.data_reader import DataReader
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider


async def _load_global_tables(config):
    storage = create_storage(config.output_storage)
    table_provider = create_table_provider(config.table_provider, storage=storage)
    reader = DataReader(table_provider)
    entities = await reader.entities()
    communities = await reader.communities()
    community_reports = await reader.community_reports()
    return entities, communities, community_reports


def query_graphrag_global(root: Path, question: str) -> tuple[str, dict]:
    cli_overrides = None  # hoặc {"output_storage": {"base_dir": "/path/to/output"}}
    config = load_config(root_dir=root, cli_overrides=cli_overrides)
    entities, communities, community_reports = asyncio.run(_load_global_tables(config))
    return asyncio.run(
        api.global_search(
            config=config,
            entities=entities,
            communities=communities,
            community_reports=community_reports,
            community_level=2,
            dynamic_community_selection=False,
            response_type="Multiple Paragraphs",
            query=question,
            verbose=False,
        )
    )


# answer, context_data = query_graphrag_global(Path("/path/to/my_graphrag_project"), "...")
```

Đối với **local search**, cần thêm `text_units`, `relationships`, và tùy chọn `covariates` — xem `_resolve_output_files` trong `packages/graphrag/graphrag/cli/query.py` để biết đúng danh sách bảng.

**Gộp vào Ragas**: mỗi khóa trong `context_data` thường là `pandas.DataFrame` — hãy nối các cột văn bản quan trọng (`full_content`, `summary`, `description`, `text`, … — tùy bảng) thành `list[str]` cho trường `retrieved_contexts`.

---

## Phần 4 — Fallback: heuristic từ artifact (không khuyến nghị cho Faithfulness)

Khi không dùng API, có thể đọc các bảng trong thư mục output được cấu hình (file cụ thể phụ thuộc `table_provider` / storage; với storage dạng file thường trùng tên logic như `entities`, `community_reports`, `text_units`, …).

Ví dụ minh họa (giữ đơn giản — **không** thay được việc lấy đúng context mà pipeline query đã chọn):

```python
import pandas as pd

OUTPUT_DIR = "./my_graphrag_project/output"

entities_df = pd.read_parquet(f"{OUTPUT_DIR}/entities.parquet")
relationships_df = pd.read_parquet(f"{OUTPUT_DIR}/relationships.parquet")
text_units_df = pd.read_parquet(f"{OUTPUT_DIR}/text_units.parquet")
community_df = pd.read_parquet(f"{OUTPUT_DIR}/community_reports.parquet")


def get_relevant_contexts(question: str, top_k: int = 3) -> list[str]:
    keywords = [w.lower() for w in question.split() if len(w) > 3]
    contexts: list[str] = []

    if "full_content" in community_df.columns:
        for _, row in community_df.iterrows():
            content = str(row.get("full_content", ""))
            if any(kw in content.lower() for kw in keywords):
                contexts.append(content[:1000])
                if len(contexts) >= top_k:
                    break

    if len(contexts) < top_k and "text" in text_units_df.columns:
        for _, row in text_units_df.iterrows():
            content = str(row.get("text", ""))
            if any(kw in content.lower() for kw in keywords):
                contexts.append(content[:500])
                if len(contexts) >= top_k:
                    break

    return contexts if contexts else ["No relevant context found"]
```

Đường dẫn `*.parquet` có thể khác nếu bạn dùng Azure Blob hoặc provider khác — khi đó hãy bám vào `output_storage` trong config thay vì hard-code `OUTPUT_DIR`.

---

## Phần 5 — Bộ câu hỏi mẫu & thu thập kết quả (CLI subprocess)

Phù hợp GraphRAG: phân biệt câu **local** (entity/fact cụ thể) và **global** (chủ đề, synth nhiều community).

```python
import subprocess
import pandas as pd

test_questions = [
    "Tên các thực thể chính trong tài liệu là gì?",
    "Thực thể X đóng vai trò gì?",
    "Các chủ đề chính trong corpus là gì?",
    "Tóm tắt các điểm then chốt.",
]

ground_truths = ["", "", "", ""]

def query_graphrag_cli(
    question: str,
    method: str,
    root: str,
    data_dir: str | None = None,
) -> dict:
    cmd = [
        "graphrag",
        "query",
        "--root",
        root,
    ]
    if data_dir:
        cmd.extend(["--data", data_dir])
    cmd.extend(
        [
            "--method",
            method,
            "--response-type",
            "Multiple Paragraphs",
            question,
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return {"question": question, "answer": result.stdout.strip(), "method": method}

results = []
for q in test_questions:
    results.append(query_graphrag_cli(q, method="global", root="/path/to/my_graphrag_project"))

for r in results:
    r["contexts"] = get_relevant_contexts(r["question"])
```

(Nếu benchmark nghiêm túc, thay khối `contexts` bằng dữ liệu từ API Phần 3.2.)

---

## Phần 6 — Chạy RAGAS Evaluation

### 6.1 Chọn metric


| Metric               | Cần gì                           | Ghi chú                                      |
| -------------------- | -------------------------------- | -------------------------------------------- |
| `Faithfulness`       | answer + contexts                | Context nên là context retrieval thật (API). |
| `ResponseRelevancy`  | question + answer (+ embeddings) | Ít phụ thuộc vào retrieval.                  |
| `LLMContextRecall`   | + ground_truth                   | Context có chứa thông tin cần không.         |
| `FactualCorrectness` | answer + reference               |                                              |
| `NoiseSensitivity`   | answer + contexts + reference    | Chi phí judge cao.                           |


Free tier / quota thấp: bắt đầu với `Faithfulness` + `ResponseRelevancy`, `max_workers` nhỏ.

### 6.2 Code đánh giá

```python
from ragas import evaluate, EvaluationDataset
from ragas.metrics import Faithfulness, ResponseRelevancy
from ragas.run_config import RunConfig

eval_samples = []
for i, r in enumerate(results):
    sample = {
        "user_input": r["question"],
        "response": r["answer"],
        "retrieved_contexts": r["contexts"],
    }
    if ground_truths[i]:
        sample["reference"] = ground_truths[i]
    eval_samples.append(sample)

eval_dataset = EvaluationDataset.from_list(eval_samples)

rate_friendly_config = RunConfig(
    timeout=120,
    max_retries=5,
    max_wait=60,
    max_workers=2,
    log_tenacity=True,
)

result = evaluate(
    dataset=eval_dataset,
    metrics=[
        Faithfulness(llm=evaluator_llm),
        ResponseRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
    ],
    llm=evaluator_llm,
    run_config=rate_friendly_config,
    show_progress=True,
)
print(result)
```

---

## Phần 7 — Phân tích kết quả

```python
import pandas as pd

df = result.to_pandas()
print(df[["user_input", "faithfulness", "response_relevancy"]].to_string())

weak = df[df["faithfulness"] < 0.5]
for _, row in weak.iterrows():
    print(row["user_input"])
```

---

## Phần 8 — So sánh các chiến lược query

GraphRAG trong repo có bốn method CLI. Benchmark có thể lặp cùng một tập câu hỏi với `global`, `local`, `drift`, `basic` rồi gom điểm Ragas vào một bảng (nhớ giữ `**retrieved_contexts**` nhất quán — tốt nhất lấy từ API từng loại).

Ví dụ khung CLI:

```python
for q in test_questions[:5]:
    for method in ["global", "local", "drift", "basic"]:
        query_graphrag_cli(q, method=method, root="/path/to/my_graphrag_project")
```

---

## Phần 9 — Chi phí & lịch chạy (tham khảo)

Chi phí **index** và **query** phụ thuộc hoàn toàn vào cỡ corpus, khối embedding, và model trong `settings.yaml` — không cố định theo “số request/file”. Khi làm benchmark:

1. Giữ `max_workers` thấp trên evaluator Ragas và trên các job song song khác để tránh 429.
2. Tách các pha: (A) chỉnh index một lần, (B) chạy tập nhỏ câu query, (C) chỉ Ragas judge.

---

## Lỗi thường gặp


| Triệu chứng                            | Gợi ý                                                                                    |
| -------------------------------------- | ---------------------------------------------------------------------------------------- |
| `Invalid method` / CLI không nhận diện | Dùng đúng `global`/`local`/`drift`/`basic` (chữ thường).                                 |
| Không đọc được output                  | Kiểm tra `output_storage` trong settings; thử `--data`.                                  |
| `429` / quota                          | Giảm `max_workers`, tăng `max_wait`; chạy tập nhỏ.                                       |
| Faithfulness thấp dù answer hay        | Context heuristic (keyword) không trùng context thật — chuyển sang API + `context_data`. |
| `Score = NaN`                          | Answer/context rỗng hoặc quá ngắn.                                                       |



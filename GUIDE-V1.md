# Hướng dẫn chạy GraphRAG

## Cách 1: Chạy từ source code (repo này)

### 1. Cài đặt

- Cài **Python 3.11** (hoặc 3.10, 3.12).
- Cài **uv**: https://docs.astral.sh/uv/

```bash
cd /home/trong/Documents/graphrag
uv sync --all-packages
```

### 2. Tạo workspace và khởi tạo cấu hình

Poe đọc cấu hình từ thư mục **hiện tại**, nên cần chạy lệnh từ **trong repo graphrag** (nơi có `pyproject.toml`), và truyền `--root` tới thư mục workspace:

```bash
# Tạo thư mục làm việc (có thể đặt bất kỳ đâu)
mkdir -p ~/graphrag_workspace

# Chạy init TỪ THƯ MỤC REPO, trỏ --root tới workspace
cd /home/trong/Documents/graphrag
uv run poe init --root /home/trong/graphrag_workspace
```

Nếu muốn đứng trong workspace mà vẫn gọi poe, chỉ rõ thư mục chứa `pyproject.toml` bằng `-C`:

```bash
cd ~/graphrag_workspace
uv run --project /home/trong/Documents/graphrag poe -C /home/trong/Documents/graphrag init --root .
```

Khi được hỏi, chọn **chat model** và **embedding model** (ví dụ: `gpt-4o-mini`, `text-embedding-3-small`).

### 3. Cấu hình API key

**Chỉ sửa file trong thư mục workspace của bạn** (ví dụ `~/graphrag_workspace`), **không** sửa bất kỳ `settings.yaml` hay `.env` nào nằm trong repo GraphRAG (những file trong repo là cho test/example, không phải cấu hình chạy của bạn).

- **File cần sửa:**  
  - `<workspace>/settings.yaml` — ví dụ: `/home/trong/graphrag_workspace/settings.yaml`  
  - `<workspace>/.env` — ví dụ: `/home/trong/graphrag_workspace/.env`

Mở `.env` trong workspace và thay `<API_KEY>` bằng API key thật:

- **OpenAI**: chỉ cần `GRAPHRAG_API_KEY=<key OpenAI của bạn>`
- **Azure OpenAI**: sửa thêm trong **`settings.yaml` của workspace** (api_base, deployment_name, v.v.) theo [get_started](docs/get_started.md).

### 3b. Cấu hình model local (LiteLLM / OpenAI-compatible API)

Nếu bạn tự host model và expose qua **LiteLLM** (hoặc API tương thích OpenAI) với `api_url`, `api_key`, `model_name`:

1. **Trong `.env` của workspace** (để tránh ghi key vào repo):

   ```
   LITELLM_API_URL=http://localhost:4000
   LITELLM_API_KEY=your-api-key
   ```

2. **Trong `settings.yaml` của workspace**, sửa hai khối `completion_models` và `embedding_models`:

   ```yaml
   completion_models:
     default_completion_model:
       type: litellm
       model_provider: openai
       model: <model_name>   # tên model trên LiteLLM của bạn, ví dụ: llama3.2, qwen2.5, gpt-4o
       auth_method: api_key
       api_key: ${LITELLM_API_KEY}
       api_base: ${LITELLM_API_URL}
       retry:
         type: exponential_backoff

   embedding_models:
     default_embedding_model:
       type: litellm
       model_provider: openai
       model: <embedding_model_name>   # tên model embedding trên LiteLLM, ví dụ: text-embedding-3-small
       auth_method: api_key
       api_key: ${LITELLM_API_KEY}
       api_base: ${LITELLM_API_URL}
       retry:
         type: exponential_backoff
   ```

   Thay `<model_name>` và `<embedding_model_name>` bằng tên model thật trên server LiteLLM của bạn. GraphRAG dùng LiteLLM với format `model_provider/model`; khi đặt `model_provider: openai` và `api_base`, mọi request sẽ gửi tới `api_base` của bạn.

3. **Ví dụ cụ thể** (chat model `my-llama`, embedding `my-embedding`, server `http://192.168.1.10:4000`):

   ```yaml
   completion_models:
     default_completion_model:
       type: litellm
       model_provider: openai
       model: my-llama
       auth_method: api_key
       api_key: ${LITELLM_API_KEY}
       api_base: ${LITELLM_API_URL}
       retry:
         type: exponential_backoff

   embedding_models:
     default_embedding_model:
       type: litellm
       model_provider: openai
       model: my-embedding
       auth_method: api_key
       api_key: ${LITELLM_API_KEY}
       api_base: ${LITELLM_API_URL}
       retry:
         type: exponential_backoff
   ```

   `.env`:

   ```
   LITELLM_API_URL=http://192.168.1.10:4000
   LITELLM_API_KEY=sk-xxx
   ```

**Lưu ý:** Model chat cần hỗ trợ **structured output** (JSON schema) vì GraphRAG dùng để trích entities/relationships. Nếu model local trả JSON lỗi format, có thể cần chỉnh prompt hoặc dùng [index method fast](docs/index/methods.md) (NLP cho bước graph, LLM cho tóm tắt).

### 3c. Cấu hình với API key Gemini (free tier)

Dùng **Google AI Studio** (Gemini API) với key miễn phí: lấy key tại [Google AI Studio](https://aistudio.google.com/) hoặc [ai.google.dev](https://ai.google.dev/).

1. **Trong `.env` của workspace**:

   ```
   GEMINI_API_KEY=your-gemini-api-key
   ```

2. **Trong `settings.yaml` của workspace**, sửa `completion_models` và `embedding_models`:

   ```yaml
   completion_models:
     default_completion_model:
       type: litellm
       model_provider: gemini
       model: gemini-1.5-flash
       auth_method: api_key
       api_key: ${GEMINI_API_KEY}
       retry:
         type: exponential_backoff

   embedding_models:
     default_embedding_model:
       type: litellm
       model_provider: gemini
       model: text-embedding-004
       auth_method: api_key
       api_key: ${GEMINI_API_KEY}
       retry:
         type: exponential_backoff
   ```

   **Chat (free tier):** có thể dùng `gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash`, `gemini-2.5-flash-lite` tùy phiên bản.  
   **Embedding:** thường dùng `text-embedding-004` hoặc `gemini-embedding-001` (đúng tên theo [LiteLLM Gemini](https://docs.litellm.ai/docs/providers/gemini)).  
   **Quan trọng:** `model_provider` phải là **`gemini`** (không dùng `google`). LiteLLM dùng prefix `gemini/` cho Google AI Studio; dùng `google` sẽ gây lỗi "LLM Provider NOT provided".

3. **Ví dụ dùng Gemini 2.0 Flash (free tier)**:

   ```yaml
   completion_models:
     default_completion_model:
       type: litellm
       model_provider: gemini
       model: gemini-2.0-flash
       auth_method: api_key
       api_key: ${GEMINI_API_KEY}
       retry:
         type: exponential_backoff

   embedding_models:
     default_embedding_model:
       type: litellm
       model_provider: gemini
       model: text-embedding-004
       auth_method: api_key
       api_key: ${GEMINI_API_KEY}
       retry:
         type: exponential_backoff
   ```

   `.env`: `GEMINI_API_KEY=AIza...` (key lấy từ AI Studio).

**Lưu ý:** Với Gemini free tier có giới hạn RPM (requests/phút). Nếu gặp rate limit, giảm tải (dataset nhỏ, hoặc dùng `--method fast`) hoặc bật billing để tăng limit.

### 3d. Cấu hình MiniMax 2.5 qua Kilocode (Kilo AI Gateway)

Nếu Gemini không đủ quota, có thể dùng **MiniMax 2.5** qua **Kilo AI Gateway** (Kilocode): API chuẩn OpenAI, một key gọi nhiều model. Gateway: [https://api.kilo.ai/api/gateway](https://api.kilo.ai/api/gateway).

1. **Lấy API key:** Đăng ký tại [Kilocode](https://kilocode.ai) / [Kilo AI](https://kilo.ai), tạo API key.

2. **Trong `.env` của workspace** (bạn cung cấp key):

   ```
   KILO_API_KEY=your-kilocode-api-key
   ```

3. **Trong `settings.yaml` của workspace** — dùng MiniMax 2.5 cho **chat** (completion). Embedding vẫn cần model khác (Kilo free có thể không có embedding); nếu quota Gemini còn ít có thể chỉ dùng Gemini cho embedding, hoặc chọn provider embedding khác.

   **Chỉ đổi completion sang MiniMax 2.5 (qua Kilo):** Dùng `model_provider: openai` + `api_base` của Kilo để gửi request tới gateway; `model` đặt đúng ID mà Kilo nhận (có thể thử `minimax/minimax-m2.5:free` hoặc theo [Kilo models](https://api.kilo.ai/api/gateway/models)).

   ```yaml
   completion_models:
     default_completion_model:
       type: litellm
       model_provider: openai
       model: minimax/minimax-m2.5:free
       auth_method: api_key
       api_key: ${KILO_API_KEY}
       api_base: https://api.kilo.ai/api/gateway
       retry:
         type: exponential_backoff

   embedding_models:
     default_embedding_model:
       # Giữ Gemini chỉ cho embedding (tốn ít quota hơn chat), hoặc đổi sang provider khác
       type: litellm
       model_provider: gemini
       model: text-embedding-004
       auth_method: api_key
       api_key: ${GEMINI_API_KEY}
       retry:
         type: exponential_backoff
   ```

   Nếu muốn **cả completion và embedding** đều qua Kilo (khi có model embedding tương thích trên gateway), đặt cùng `api_base` và `api_key`, đổi `model` embedding theo [danh sách model Kilo](https://api.kilo.ai/api/gateway/models).

4. **Ví dụ dùng trọn MiniMax 2.5 (chat) + Gemini (embedding):**

   `.env`:

   ```
   KILO_API_KEY=your-kilocode-key
   GEMINI_API_KEY=your-gemini-key
   ```

   `settings.yaml` (đoạn models):

   ```yaml
   completion_models:
     default_completion_model:
       type: litellm
       model_provider: openai
       model: minimax/minimax-m2.5:free
       auth_method: api_key
       api_key: ${KILO_API_KEY}
       api_base: https://api.kilo.ai/api/gateway
       retry:
         type: exponential_backoff

   embedding_models:
     default_embedding_model:
       type: litellm
       model_provider: gemini
       model: text-embedding-004
       auth_method: api_key
       api_key: ${GEMINI_API_KEY}
       retry:
         type: exponential_backoff
   ```

**Lưu ý:** Model ID trên Kilo là `minimax/minimax-m2.5:free` (free tier). GraphRAG ghép model thành `model_provider/model`. Nếu gateway báo sai tên model, thử đổi completion thành `model_provider: minimax` và `model: minimax-m2.5:free` (khi đó LiteLLM gửi đúng chuỗi `minimax/minimax-m2.5:free`), vẫn giữ `api_base: https://api.kilo.ai/api/gateway` và `api_key: ${KILO_API_KEY}`. Xem thêm [Kilo models](https://kilo.ai/docs/gateway/models-and-providers).

### 4. Thêm tài liệu để index

```bash
# Ví dụ: tải sách mẫu
curl -o ./input/book.txt https://www.gutenberg.org/cache/epub/24022/pg24022.txt

# Hoặc copy bất kỳ file .txt vào thư mục input/
```

### 5. Chạy indexing

Chạy **từ thư mục repo** (nơi có `pyproject.toml`), trỏ `--root` tới workspace:

```bash
cd /home/trong/Documents/graphrag
uv run poe index --root /home/trong/graphrag_workspace
```

Index **standard** (dùng LLM đầy đủ) có thể chạy vài phút. Kết quả nằm trong `<workspace>/output/` (các file parquet).

Để chạy nhanh hơn (ít gọi LLM):

```bash
uv run poe index --root /home/trong/graphrag_workspace --method fast
```

**Nếu index “treo” lâu ở bước extract_graph (ví dụ 41/42):**

- Pipeline gọi LLM cho **từng text unit** (mỗi chunk). Unit cuối có thể **lỗi** (rate limit, timeout) rồi vào **retry exponential backoff**: chờ 2s, 4s, 8s, 16s… (mặc định tới 7 lần) nên có thể chờ vài phút trước khi báo lỗi hoặc thử lại.
- **Cách xử lý:** (1) Chạy với `--verbose` / `-v` để xem log (có báo lỗi hay đang retry). (2) Giảm tải: trong `settings.yaml` thêm `concurrent_requests: 5` (hoặc 3) ở root để ít request đồng thời, tránh bị gateway rate limit. (3) Giới hạn retry: trong `completion_models.default_completion_model` thêm `retry: { type: exponential_backoff, max_retries: 3, base_delay: 2 }` để không chờ quá lâu khi lỗi.

### 6. Chạy query

Chạy từ thư mục repo, `--root` trỏ tới workspace.

**Global search** (câu hỏi tổng quan):

```bash
cd /home/trong/Documents/graphrag
uv run poe query "What are the top themes in this story?" --root /home/trong/graphrag_workspace
```

**Local search** (câu hỏi cụ thể về entity):

```bash
uv run poe query "Who is Scrooge and what are his main relationships?" --root /home/trong/graphrag_workspace --method local
```

**Nếu global search trả:** `I am sorry but I am unable to answer this question given the provided data.`

- **Không phải lỗi crash.** Global search có bước **map** (LLM đọc từng batch community report, trả JSON có các “điểm” + **điểm số score**). Bước **reduce** chỉ dùng các điểm có **score > 0**. Nếu **tất cả score = 0** hoặc JSON map **không đúng format** (parse lỗi → coi như không có điểm), GraphRAG trả câu cố định trên.
- **Thường gặp khi:** model (ví dụ MiniMax qua Kilo) **không trả JSON đúng schema** ở bước map, hoặc báo “không liên quan” → score 0 hết. Chạy `uv run poe query ... --verbose` để xem log cảnh báo: *"All map responses have score 0"*.
- **Thử:** (1) **`--method local`** với câu hỏi gắn entity cụ thể. (2) **`--community-level 0` hoặc `1`** (mặc định 2) để thử mức community khác. (3) Thêm **completion model** (ví dụ Gemini) chỉ cho query: trong `settings.yaml` thêm một `completion_models` mới và đặt `global_search.completion_model_id` trỏ tới model đó — model tốt với **JSON structured output** thường map/reduce ổn hơn MiniMax. (4) API Python có thể bật `allow_general_knowledge` — xem [global_search](docs/query/global_search.md).

---

## Cách 2: Cài từ PyPI (không dùng source)

```bash
mkdir graphrag_quickstart && cd graphrag_quickstart
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install graphrag
graphrag init
# Sửa .env (GRAPHRAG_API_KEY), thêm file vào input/
graphrag index
graphrag query "What are the top themes?" --method global
```

---

## Lệnh từ repo (tóm tắt)

**Chạy từ thư mục repo** (`cd /home/trong/Documents/graphrag`), thay `<path>` bằng đường dẫn workspace (ví dụ `/home/trong/graphrag_workspace`):

| Lệnh | Mô tả |
|------|--------|
| `uv run poe init --root <path>` | Tạo cấu hình tại thư mục chỉ định |
| `uv run poe index --root <path>` | Index dữ liệu (standard) |
| `uv run poe index --root <path> --method fast` | Index nhanh (NLP + LLM) |
| `uv run poe query "câu hỏi" --root <path>` | Hỏi (mặc định global) |
| `uv run poe query "câu hỏi" --root <path> --method local` | Hỏi theo local search |
| `uv run poe prompt-tune --root <path>` | Tinh chỉnh prompt theo dữ liệu |

Nếu muốn chạy khi **đang ở trong workspace**, thêm `-C <đường_dẫn_repo>` để poe tìm đúng `pyproject.toml`:  
`uv run --project <repo> poe -C <repo> init --root .`

---

## Giao diện web (Unified Search App) — chat trên trình duyệt

Repo có **Streamlit** để nhập câu hỏi trên web (thay vì `poe query` trong terminal), so sánh Basic / Local / Global / Drift.

### Yêu cầu

- Đã **index xong** (có `output/`, `settings.yaml`, `prompts/`, `.env` trong workspace).

### Cách nhanh (một workspace đã index)

1. **Tạo thư mục “projects”** và **một thư mục con** chứa bản sao (hoặc symlink) workspace:

   ```bash
   mkdir -p ~/graphrag_projects/mydata
   # Cách A: copy (an toàn)
   cp -r /home/trong/graphrag_workspace/settings.yaml /home/trong/graphrag_workspace/.env \
         /home/trong/graphrag_workspace/output /home/trong/graphrag_workspace/prompts \
         ~/graphrag_projects/mydata/
   # Cách B: symlink (không tốn dung lượng, vẫn dùng cùng index)
   # rm -rf ~/graphrag_projects/mydata && mkdir -p ~/graphrag_projects
   # ln -s /home/trong/graphrag_workspace ~/graphrag_projects/mydata
   ```

2. **Tạo `listing.json`** trong `~/graphrag_projects/` (trường `path` = tên thư mục con):

   ```bash
   cat > ~/graphrag_projects/listing.json << 'EOF'
   [{
       "key": "my-dataset",
       "path": "mydata",
       "name": "Dataset của tôi",
       "description": "Index GraphRAG",
       "community_level": 2
   }]
   EOF
   ```

3. **Chạy web** (luôn từ thư mục `unified-search-app`):

   ```bash
   cd /home/trong/Documents/graphrag/unified-search-app
   uv sync
   export DATA_ROOT=/home/trong/graphrag_projects
   uv run streamlit run app/home_page.py
   ```

   App dùng **graphrag từ monorepo** (`../packages/graphrag`), cùng phiên bản với `poe index` — `settings.yaml` có `cache: json`, `vector_store: lancedb` mới đọc được. *(Lệnh `uv run poe start` cần `uv sync --extra dev`.)*

4. Mở trình duyệt: **http://localhost:8501**

### Chat trên giao diện

1. **Sidebar (trái):** chọn dataset trong dropdown, bật ít nhất một loại search (**Global**, **Local**, …).
2. Ô **“Ask a question to compare the results”**: gõ câu hỏi → gửi.
3. Tab **Search**: xem câu trả lời từng loại (Global / Local / …) và citations.
4. **Suggest some questions**: sinh câu hỏi mẫu (cũng gọi LLM).
5. Tab **Community Explorer**: xem danh sách community reports.

⚠️ App demo, không phải sản phẩm chính thức. Nếu lỗi import, chạy `uv sync` trong `unified-search-app` và đảm bảo `DATA_ROOT` là **đường dẫn tuyệt đối** tới thư mục chứa `listing.json`.

---

## Xem knowledge graph (Gephi)

Không có giao diện vẽ graph sẵn trong repo. Bạn có thể **xuất graph** rồi mở bằng công cụ ngoài:

1. Bật snapshot GraphML trong `settings.yaml`: `snapshots: graphml: true`
2. Chạy index; trong `output/` sẽ có file **graph.graphml**
3. Cài [Gephi](https://gephi.org), mở `graph.graphml` và chỉnh layout/color theo [docs/visualization_guide.md](docs/visualization_guide.md).

---

## Lưu ý

- Indexing tốn LLM (token). Nên thử với dataset nhỏ hoặc model rẻ (ví dụ `gpt-4o-mini`) trước.
- Đọc thêm: [docs/get_started.md](docs/get_started.md), [docs/config/init.md](docs/config/init.md).

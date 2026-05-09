1. Chuyển file docx sang txt
```
libreoffice --headless --convert-to txt "Bộ-luật-45-2019-QH14.docx"
```
2. Đưa vào workspace của graph rag
```
cp "Bộ-luật-45-2019-QH14.txt" /home/trong/graphrag_workspace/input/
```
3. Chạy index file
```
cd /home/trong/Documents/graphrag
uv run poe index --root /home/trong/graphrag_workspace --verbose 2>&1
```
4. Query
```
uv run poe query "Quyền và nghĩa vụ của người lao động là gì?" --root /home/trong/graphrag_workspace --method local
```
5. Visualize 
```
cd /home/trong/Documents/graphrag/packages/graphrag && uv run python /home/trong/Documents/graphrag/scripts/visualize_graphrag_workspace.py --workspace /home/trong/graphrag_workspace
```
Visualize v2
```
cd /home/trong/Documents/graphrag/packages/graphrag
uv run --with scipy python /home/trong/Documents/graphrag/scripts/visualize_graphrag_workspace.py --workspace /home/trong/graphrag_workspace
```
6. Index từng file & update graph
```
uv run python scripts/index_per_file_with_usage.py \
  --repo-root /home/trong/Documents/graphrag \
  --workspace-root /home/trong/graphrag_workspace \
  --source-dir /home/trong/Documents/graphrag/data \
  --method standard
```
CONFIG
```
completion_models:
  default_completion_model:
    type: litellm
    model_provider: openai
    model: kilo-auto/free
    auth_method: api_key
    api_key: ${KILO_API_KEY}
    api_base: https://api.kilo.ai/api/gateway
    retry:
      type: exponential_backoff

embedding_models:
  default_embedding_model:
    model_provider: gemini
    model: gemini-embedding-2-preview
    auth_method: api_key
    api_key: ${GEMINI_API_KEY}
    retry:
      type: exponential_backoff
```
7. Index updating tuần tự
chú ý cần enable neo4j trong env
```bash
cd /home/trong/Documents/graphrag
set -a && source /home/trong/graphrag_workspace/.env && set +a
uv run python scripts/index_per_file.py   --source-dir /home/trong/Documents/graphrag/data/txt   --pattern "BLLĐ-45-2019.txt"
```
8. Sync data lên Neo4j
```bash
cd /home/trong/Documents/graphrag
set -a && source /home/trong/graphrag_workspace/.env && set +a
uv run python scripts/index_per_file.py \
  --sync-only \
  --workspace-root /home/trong/graphrag_workspace
```
Dry-run (chỉ in kế hoạch, không gửi Neo4j):
```bash
uv run python scripts/index_per_file.py \
  --sync-only \
  --workspace-root /home/trong/graphrag_workspace \
  --dry-run
```
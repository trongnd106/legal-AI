1. Khởi động Neo4j

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/123456aA@ \
  neo4j:5
```

Mở trình duyệt, truy cập [http://localhost:7474](http://localhost:7474)

1. Đánh index từng file -> auto sync Neo4j

```bash
cd /home/trong/Documents/graphrag

set -a && source /home/trong/graphrag_workspace/.env && set +a

uv run python scripts/index_per_file.py \
  --source-dir /home/trong/Documents/graphrag/data \
  --method standard
```

hoặc chỉ 1 file cụ thể:

```bash
uv run python scripts/index_per_file.py \
  --source-dir /home/trong/Documents/graphrag/data \
  --pattern "ten_file.txt"
```

Không chạy thật, không sync:

```bash
uv run python scripts/index_per_file.py --dry-run
```

Chạy nhưng không sync Neo4j:

```bash
uv run python scripts/index_per_file.py --no-neo4j
```

1. Check output

Trên Neo4j Browser - chạy Cypher:

```
// Xem tổng số node theo loại
MATCH (n) RETURN labels(n) AS type, count(n) AS total ORDER BY total DESC;

// Xem 10 Entity đầu tiên
MATCH (e:Entity) RETURN e.title, e.type, e.description LIMIT 10;

// Xem các quan hệ của 1 entity
MATCH (e:Entity {title: "Bộ Lao Động"})-[r:RELATED_TO]-(other)
RETURN e.title, r.description, other.title LIMIT 20;

// Xem entity theo file nguồn
MATCH (e:Entity) WHERE e.source_file = "ten_file.txt"
RETURN e.title, e.type LIMIT 20;

// Xem community reports
MATCH (cr:CommunityReport)
RETURN cr.title, cr.summary, cr.rank ORDER BY cr.rank DESC LIMIT 10;
```

Trên disk - xem parquet:

```bash
ls /home/trong/graphrag_workspace/output/
```


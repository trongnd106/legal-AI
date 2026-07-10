# Neo4j Graph — Thống kê

## Kết nối


| Thông số | Giá trị                                        |
| -------- | ---------------------------------------------- |
| URI      | `bolt://localhost:7687`                        |
| User     | `neo4j`                                        |
| Pass     | `123456aA@`                                    |
| Browser  | [http://localhost:7474](http://localhost:7474) |


---

## 1. Thống kê nodes

### 1.1. Số lượng từng label

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```


| Label              | Số lượng | Ghi chú                        |
| ------------------ | -------- | ------------------------------ |
| `:Entity`          | 5.124    | Entity ngữ nghĩa L2 (14+ loại) |
| `:Khoan`           | 1.982    | Khoản con của Điều             |
| `:Community`       | 903      | Community từ Leiden clustering |
| `:CommunityReport` | 901      | Báo cáo community              |
| `:TextUnit`        | 599      | Text units (≈ 1 Điều / chunk)  |
| `:Dieu`            | 560      | Điều luật                      |
| `:Chuong`          | 52       | Chương trong văn bản           |
| `:VanBan`          | 7        | Văn bản pháp luật gốc          |


### 1.2. Các type trên `:Entity`

```cypher
MATCH (n:Entity)
WITH n.type AS entity_type, count(*) AS cnt
RETURN entity_type, cnt
ORDER BY cnt DESC
```


| `entity_type`         | Count |
| --------------------- | ----- |
| `HANHVI`              | 2.439 |
| `CHUTHE`              | 637   |
| `THOIGIOLAMVIEC`      | 300   |
| `COQUAN`              | 259   |
| `CHEDOBAOHIEM`        | 216   |
| `CHETAI`              | 203   |
| `HOPDONGLAODONG`      | 195   |
| `TRALUONG`            | 188   |
| `ANTOANVESINHLAODONG` | 181   |
| `TIENLUONG`           | 178   |
| `NGHIPHEP`            | 162   |
| `XULYKYLUAT`          | 96    |
| `TROCAPTHOIVIEC`      | 55    |
| `VANBAN`              | 3     |


### 1.3. Properties trên mỗi label

`**:Entity`**

```cypher
MATCH (n:Entity)
RETURN keys(n) AS properties
LIMIT 1
```

→ `['human_readable_id', 'id', 'type', 'text_unit_ids', 'title', 'description']`

`**:Dieu**`

```cypher
MATCH (n:Dieu)
RETURN keys(n) AS properties
LIMIT 1
```

→ `['van_ban', 'description', 'type', 'chuong_so', 'id', 'norm_type', 'human_readable_id', 'text_unit_ids', 'title']`

---

## 2. Thống kê relationships

### 2.1. Số lượng từng type

```cypher
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS cnt
ORDER BY cnt DESC
```


| Type          | Count | Ghi chú                                    |
| ------------- | ----- | ------------------------------------------ |
| `:RELATED_TO` | 7.890 | Quan hệ ngữ nghĩa L2 giữa các Entity       |
| `:contains`   | 2.702 | Quan hệ cấu trúc L1 (VB→Chương→Điều→Khoản) |
| `:guided_by`  | 8     | Quan hệ tham chiếu giữa các văn bản        |
| `:issued_by`  | 7     | Văn bản do cơ quan nào ban hành            |


### 2.2. Chi tiết từng loại L1

```cypher
MATCH (src)-[r]->(tgt)
WHERE type(r) <> "RELATED_TO"
RETURN labels(src)[0] AS src_label,
       type(r) AS rel_type,
       labels(tgt)[0] AS tgt_label,
       count(*) AS cnt
ORDER BY cnt DESC
```


| Source → Rel → Target              | Count |
| ---------------------------------- | ----- |
| `:Dieu` -[:contains]→ `:Khoan`     | 2.069 |
| `:Chuong` -[:contains]→ `:Dieu`    | 581   |
| `:VanBan` -[:contains]→ `:Chuong`  | 52    |
| `:VanBan` -[:guided_by]→ `:VanBan` | 8     |
| `:VanBan` -[:issued_by]→ `:Entity` | 7     |


---

## 3. Query

### 3.1. Xem entity lỗi (type sai)

```cypher
// Các entity không thuộc 14 domain type chuẩn
MATCH (n:Entity)
WHERE n.type NOT IN [
  'HANHVI', 'CHUTHE', 'THOIGIOLAMVIEC', 'COQUAN',
  'CHEDOBAOHIEM', 'CHETAI', 'HOPDONGLAODONG',
  'TRALUONG', 'ANTOANVESINHLAODONG', 'TIENLUONG',
  'NGHIPHEP', 'XULYKYLUAT', 'TROCAPTHOIVIEC'
]
RETURN n.id, n.title, n.type
```

### 3.2. Kiểm tra cấu trúc phân cấp văn bản

```cypher
// Hệ thống phân cấp VanBan → Chuong → Dieu
MATCH path = (vb:VanBan)-[:contains*1..3]->(leaf)
RETURN path
LIMIT 50
```

```cypher
// Tất cả Điều của một văn bản cụ thể
MATCH (vb:VanBan {id: '45_2019_QH14'})-[:contains]->(:Chuong)-[:contains]->(d:Dieu)
RETURN d.id, d.title
ORDER BY d.id
```

### 3.3. Entity và các kết nối

```cypher
// Xem entity kèm các relationship xung quanh
MATCH (n:Entity {type: 'HANHVI'})-[r:RELATED_TO]-(m:Entity)
RETURN n.title, type(r), m.title
LIMIT 100
```

```cypher
// Entity có nhiều kết nối nhất (hub)
MATCH (n:Entity)
RETURN n.title, n.type, size((n)-[:RELATED_TO]-()) AS degree
ORDER BY degree DESC
LIMIT 10
```

### 3.4. Cơ quan ban hành văn bản

```cypher
MATCH (vb:VanBan)-[:issued_by]->(cq:Entity)
RETURN vb.id AS van_ban, cq.title AS co_quan_ban_hanh
```

### 3.5. Tham chiếu chéo giữa các văn bản

```cypher
MATCH (src:VanBan)-[:guided_by]->(tgt:VanBan)
RETURN src.id, tgt.id
```

### 3.6. Đếm toàn bộ đồ thị (dùng cho verification)

```cypher
// Tổng nodes
MATCH (n) RETURN count(n) AS total_nodes

// Tổng relationships
MATCH ()-[r]->() RETURN count(r) AS total_relations
```

### 3.7. Sample data để demo

```cypher
// Lấy 5 entity mẫu
MATCH (n:Entity)
RETURN n.title, n.type, substring(n.description, 0, 100) AS desc_short
LIMIT 5

// Lấy 5 Điều mẫu
MATCH (n:Dieu)
RETURN n.id, n.title
LIMIT 5
```

---

## 4. Đối chiếu với số liệu


| Hạng mục              | Neo4j |
| --------------------- | ----- |
| Tổng entities (L1+L2) | 7.725 |
| L2 entities           | 5.124 |
| L1 structural nodes   | 2.601 |
| L2 relationships      | 7.890 |
| L1 relationships      | 2.717 |
| Communities           | 903   |
| Text units            | 599   |

---

## 5. Lưu ý khi query

- `**LIMIT` bắt buộc** trên Neo4j Browser khi query graph để tránh crash
- **Cypher-Shell (CLI)** không hiển thị graph — chỉ dùng được query text
- **Browser** ([http://localhost:7474](http://localhost:7474)) tự động vẽ graph khi `RETURN` node/relationship
- **Properties dạng mảng** (`text_unit_ids`) có thể dùng `UNWIND` để phân rã


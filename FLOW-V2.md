### 1. Collect & normalize data
Run script
```bash
cd /home/trong/Documents/graphrag && python3 scripts/01_prepare_data.py --verify 2>&1
```
hoặc
```bash
python3 scripts/01_prepare_data.py --only BLLĐ-45-2019.txt --verify
```
Verify mục context, norm types, key articles
```bash
cd /home/trong/Documents/graphrag && python3 -c "
import json

# Kiểm tra Điều có Mục
bllđ = [json.loads(l) for l in open('data/labor-law/chunks/BLLĐ_2019.jsonl', encoding='utf-8')]

# Thống kê Mục
with_muc = [r for r in bllđ if r['muc_so']]
print(f'Điều có Mục: {len(with_muc)} / {len(bllđ)}')
if with_muc:
    r = with_muc[0]
    print(f'  Ví dụ: Điều {r[\"so_dieu\"]} — Chương {r[\"chuong_so\"]} Mục {r[\"muc_so\"]} ({r[\"ten_muc\"]})')

# Thống kê norm_type
from collections import Counter
norms = Counter(r['norm_type'] for r in bllđ)
print(f'Norm types: {dict(norms)}')

# Kiểm tra Điều 46 (trợ cấp thôi việc) — test case LD010
d46 = next((r for r in bllđ if r['so_dieu'] == 46), None)
if d46:
    print(f'\nĐiều 46: {d46[\"tieu_de\"]} | norm={d46[\"norm_type\"]} | {len(d46[\"khoans\"])} Khoản')
    for k in d46['khoans']:
        print(f'  Khoản {k[\"so\"]}: {k[\"noi_dung\"][:100]}')

# Kiểm tra Điều 35 (đơn phương chấm dứt)
d35 = next((r for r in bllđ if r['so_dieu'] == 35), None)
if d35:
    print(f'\nĐiều 35: {d35[\"tieu_de\"]} | norm={d35[\"norm_type\"]} | {len(d35[\"khoans\"])} Khoản')
" 2>&1
```
Check full record schema for Điều 13
```bash
cd /home/trong/Documents/graphrag && python3 -c "
import json

# Kiểm tra sample record đầy đủ schema
bllđ = [json.loads(l) for l in open('data/labor-law/chunks/BLLĐ_2019.jsonl', encoding='utf-8')]
r = next(r for r in bllđ if r['so_dieu'] == 13)
# In tất cả field, bỏ noi_dung dài
sample = {k: v for k, v in r.items() if k != 'noi_dung'}
sample['khoans'] = r['khoans'][:1]  # chỉ khoản đầu
print(json.dumps(sample, ensure_ascii=False, indent=2))
" 2>&1
```
Results
Tổng 7 file: 
- 581 Điều
- 2069 Khoản
- 1705 Điểm
Trong đó BLLĐ 2019 chứa: 220 Điều, 645 Khoản, 287 Điểm

### 2. Ontology Design
Run merge script in verify mode
```bash
cd /home/trong/Documents/graphrag && python3 scripts/02_merge_structural_graph.py --verify
```
Run merge script in dry-run mode
```bash
cd /home/trong/Documents/graphrag && python3 scripts/02_merge_structural_graph.py --dry-run
```


Important
```bash
/home/trong/.cursor/projects/home-trong-Documents-graphrag/canvases/benchmark-strategy.canvas.tsx
/home/trong/.cursor/projects/home-trong-Documents-graphrag/canvases/kg-improvements.canvas.tsx
```
### 1. Dùng python
Cài thư viện:
```bash
pip install pandas pyarrow
```
Đọc file:
```bash
import pandas as pd

df = pd.read_parquet("output/entities.parquet")
print(df.head())
```
### 2. Convert sang CSV
```bash
df = pd.read_parquet("output/entities.parquet")
df.to_csv("entities.csv", index=False)
```
### 3. Dùng CLI
Cài đặt:
```bash
pip install parquet-tools
```
Xem schema:
```bash
parquet-tools schema output/entities.parquet
```
Xem data:
```bash
parquet-tools head output/entities.parquet
```
### 4. Dùng DuckDB
Cài: 
```bash
pip install duckdb
```
Chạy:
```bash
duckdb
```
Query trực tiếp:
```bash
SELECT * FROM 'output/entities.parquet' LIMIT 10;
```
### 5. GUI (DBeaver, Apache Superset)
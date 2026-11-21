# DuckDB benchmark

Machine: Linux-6.18.44-fc-v726-x86_64-with-glibc2.39, Python 3.13.18, x86_64. Median of 5 runs, through the same locked-down `DatasetStore.query` path the agents use.

## 100,000 rows

Ingest (write parquet + register): 0.65s

| Query | Median (ms) | Max (ms) |
|---|---|---|
| total revenue (full scan) | 22 | 37 |
| revenue by region (group by) | 24 | 25 |
| monthly trend (date + group by) | 41 | 42 |
| region x category (2-key group by) | 29 | 32 |
| top 10 products (filter + sort) | 31 | 35 |

## 1,000,000 rows

Ingest (write parquet + register): 4.97s

| Query | Median (ms) | Max (ms) |
|---|---|---|
| total revenue (full scan) | 40 | 47 |
| revenue by region (group by) | 51 | 54 |
| monthly trend (date + group by) | 147 | 149 |
| region x category (2-key group by) | 77 | 99 |
| top 10 products (filter + sort) | 48 | 56 |


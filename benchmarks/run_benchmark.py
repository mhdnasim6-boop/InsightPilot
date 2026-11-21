"""Benchmark the analytics engine (DuckDB) on synthetic sales data.

This measures ONLY the SQL layer, which does all the arithmetic in InsightPilot. It does not measure LLM speed.
Usage:  python benchmarks/run_benchmark.py [--sizes 100000 1000000] [--runs 5]
"""
import argparse
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from insightpilot.config import Settings  # noqa: E402
from insightpilot.data.store import DatasetStore  # noqa: E402

QUERIES = {
    "total revenue (full scan)": "SELECT SUM(Revenue) AS total FROM data",
    "revenue by region (group by)": "SELECT Region, SUM(Revenue) AS revenue FROM data GROUP BY Region ORDER BY revenue DESC",
    "monthly trend (date + group by)": "SELECT strftime(date_trunc('month', CAST(Order_Date AS DATE)), '%Y-%m') AS month, SUM(Revenue) AS revenue FROM data GROUP BY 1 ORDER BY 1",
    "region x category (2-key group by)": "SELECT Region, Product_Category, SUM(Revenue) AS revenue, AVG(Profit) AS avg_profit FROM data GROUP BY 1, 2 ORDER BY 3 DESC",
    "top 10 products (filter + sort)": "SELECT Product, SUM(Revenue) AS revenue FROM data WHERE Quantity > 0 GROUP BY Product ORDER BY revenue DESC LIMIT 10",
}


def make_df(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    regions = np.array(["North", "South", "East", "West"])
    cats = np.array(["Electronics", "Furniture", "Clothing", "Office Supplies"])
    qty = rng.integers(1, 20, n)
    price = rng.uniform(5, 500, n).round(2)
    days = rng.integers(0, 365, n)
    return pd.DataFrame({
        "Order_ID": np.arange(n), "Order_Date": (pd.Timestamp("2025-01-01") + pd.to_timedelta(days, unit="D")).strftime("%Y-%m-%d"),
        "Region": regions[rng.integers(0, 4, n)], "Product_Category": cats[rng.integers(0, 4, n)],
        "Product": np.array([f"P{i}" for i in range(200)])[rng.integers(0, 200, n)],
        "Quantity": qty, "Revenue": (qty * price).round(2), "Profit": (qty * price * 0.3).round(2)})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[100_000, 1_000_000])
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()
    lines = [f"# DuckDB benchmark", "", f"Machine: {platform.platform()}, Python {platform.python_version()}, "
             f"{platform.processor() or 'cpu n/a'}. Median of {args.runs} runs, through the same locked-down `DatasetStore.query` path the agents use.", ""]
    with tempfile.TemporaryDirectory() as tmp:
        store = DatasetStore(Settings.from_env().with_overrides(data_dir=tmp, sql_timeout_seconds=120))
        for n in args.sizes:
            t0 = time.perf_counter()
            ds = store.create_from_dataframe(f"bench_{n}.csv", make_df(n))
            load = time.perf_counter() - t0
            lines += [f"## {n:,} rows", "", f"Ingest (write parquet + register): {load:.2f}s", "", "| Query | Median (ms) | Max (ms) |", "|---|---|---|"]
            for name, sql in QUERIES.items():
                times = []
                for _ in range(args.runs):
                    t = time.perf_counter()
                    store.query(ds, sql)
                    times.append((time.perf_counter() - t) * 1000)
                lines.append(f"| {name} | {statistics.median(times):.0f} | {max(times):.0f} |")
            lines.append("")
    text = "\n".join(lines)
    print(text)
    out = Path(__file__).parent / "results.md"
    out.write_text(text + "\n")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()

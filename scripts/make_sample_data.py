"""Regenerate sample_data/sales.csv (deterministic)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from insightpilot.data.sample import generate_sales  # noqa: E402

df, planted = generate_sales(2000, seed=42)
out = Path(__file__).resolve().parent.parent / "sample_data" / "sales.csv"
out.parent.mkdir(exist_ok=True)
df.to_csv(out, index=False)
print(f"wrote {out} with {len(df)} rows; planted issues: {planted}")

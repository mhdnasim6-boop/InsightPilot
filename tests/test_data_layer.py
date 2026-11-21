import pytest

from insightpilot.data.kpis import compute_kpis
from insightpilot.data.sample import generate_sales
from insightpilot.data.sql_guard import UnsafeSQLError, validate_select_only
from insightpilot.data.store import DatasetError, SQLExecutionError
from insightpilot.tools.cleaning_tools import apply_fixes, detect_candidate_fixes, finalise_fixes, profile_dataframe


@pytest.mark.parametrize("sql", ["SELECT 1", "select a from data", "WITH x AS (SELECT 1) SELECT * FROM x", "SELECT 1;"])
def test_guard_allows_select(sql):
    assert validate_select_only(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE data", "DELETE FROM data", "SELECT 1; DROP TABLE data", "COPY data TO 'x.csv'", "ATTACH 'x.db'",
    "INSERT INTO data VALUES (1)", "SELECT * FROM read_csv('/etc/passwd')", "PRAGMA version", "", "UPDATE data SET a=1",
    "SELECT 1 /* x */; SELECT 2", "INSTALL httpfs"])
def test_guard_blocks_unsafe(sql):
    with pytest.raises(UnsafeSQLError):
        validate_select_only(sql)


def test_guard_ignores_keywords_inside_strings():
    assert validate_select_only("SELECT 'drop table' AS note")


def test_store_roundtrip_and_query(store, sales_df):
    ds = store.create_from_dataframe("sales.csv", sales_df)
    assert store.meta(ds)["rows"] == len(sales_df)
    res = store.query(ds, "SELECT COUNT(*) AS n FROM data")
    assert res["rows"][0][0] == len(sales_df)
    assert store.schema(ds)["rows"] == len(sales_df)


def test_store_blocks_filesystem_and_writes(store, sales_df):
    ds = store.create_from_dataframe("sales.csv", sales_df)
    for bad in ("SELECT * FROM read_csv('/etc/passwd')", "SELECT * FROM '/etc/passwd'", "SELECT * FROM glob('/*')"):
        with pytest.raises((UnsafeSQLError, SQLExecutionError)):
            store.query(ds, bad)
    with pytest.raises(UnsafeSQLError):
        store.query(ds, "DELETE FROM data")


def test_row_limit_truncates(store, sales_df):
    ds = store.create_from_dataframe("s.csv", sales_df)
    res = store.query(ds, "SELECT * FROM data", max_rows=10)
    assert res["row_count"] == 10 and res["truncated"]


def test_upload_rejects_garbage(store):
    with pytest.raises(DatasetError):
        store.create_dataset("empty.csv", b"")
    with pytest.raises(DatasetError):
        store.create_dataset("notes.txt", b"hello")


def test_column_names_normalised(store):
    ds = store.create_dataset("x.csv", b"Order Date,Total $\n2025-01-01,5\n")
    assert store.meta(ds)["columns"] == ["Order_Date", "Total"] or all(" " not in c for c in store.meta(ds)["columns"])


def test_cleaning_finds_exactly_the_planted_issues():
    df, planted = generate_sales(n_rows=2000, seed=42, with_issues=True)
    fixes = {(f["op"], f.get("column")): f for f in finalise_fixes(df, detect_candidate_fixes(df))}
    assert fixes[("remove_duplicates", None)]["affected_rows"] == planted["duplicates"]
    assert fixes[("remove_invalid", "Quantity")]["affected_rows"] == planted["negative_quantity"]
    assert fixes[("fill_missing", "Discount")]["affected_rows"] == planted["missing_discount"]
    assert any(op == "convert_type" for op, _ in fixes)


def test_applying_fixes_removes_problems():
    df, _ = generate_sales(n_rows=800, seed=3, with_issues=True)
    fixes = finalise_fixes(df, detect_candidate_fixes(df))
    out, logs = apply_fixes(df, fixes)
    p = profile_dataframe(out)
    assert p["duplicate_rows"] == 0 and (out["Quantity"] >= 0).all() and out["Discount"].isna().sum() == 0
    assert all(l["status"] == "applied" for l in logs)


def test_clean_data_only_needs_date_conversion(clean_sales_df):
    ops = {f["op"] for f in finalise_fixes(clean_sales_df, detect_candidate_fixes(clean_sales_df))}
    assert ops <= {"convert_type"}      # no duplicates, invalid values or missing values to fix


def test_invalid_fix_is_rejected(sales_df):
    assert finalise_fixes(sales_df, [{"op": "fill_missing", "column": "NoSuchColumn", "strategy": "median"}]) == []


def test_kpis_match_pandas(store, clean_sales_df):
    ds = store.create_from_dataframe("s.csv", clean_sales_df)
    k = compute_kpis(store, ds)
    assert k["kpis"]["revenue"] == pytest.approx(clean_sales_df["Revenue"].sum(), rel=1e-9)
    assert k["by_region"]["rows"][0][0] == clean_sales_df.groupby("Region")["Revenue"].sum().idxmax()

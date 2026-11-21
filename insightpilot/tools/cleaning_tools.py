"""Deterministic data-cleaning tools (pandas).

The Data Cleaning Agent's LLM only *proposes* fixes from a fixed menu. Everything here either
measures a problem or applies one approved fix; nothing is changed silently.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from ..data.store import jsonable

KEY_MEASURE = re.compile(r"revenue|sales|amount|profit|cost|total", re.I)
NON_NEGATIVE = re.compile(r"quantity|qty|units|price", re.I)
OP_ORDER = {"convert_type": 0, "remove_duplicates": 1, "remove_invalid": 2, "drop_missing_rows": 3, "fill_missing": 4}


def _is_num(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _is_text(s: pd.Series) -> bool:
    return bool(pd.api.types.is_string_dtype(s) or s.dtype == object)


def profile_dataframe(df: pd.DataFrame) -> dict:
    n = len(df)
    cols = []
    for c in df.columns:
        s = df[c]
        miss = int(s.isna().sum())
        info: dict[str, Any] = {
            "name": c, "dtype": str(s.dtype), "missing": miss,
            "missing_pct": round(100.0 * miss / n, 2) if n else 0.0,
            "unique": int(s.nunique(dropna=True)),
            "sample": [jsonable(v) for v in s.dropna().head(3).tolist()],
        }
        if _is_num(s) and s.notna().any():
            info["min"], info["max"] = float(s.min()), float(s.max())
        cols.append(info)
    return {"rows": n, "duplicate_rows": int(df.duplicated().sum()), "columns": cols}


def _date_parse_rate(s: pd.Series) -> float:
    nn = s.dropna().astype(str)
    if nn.empty or pd.to_numeric(nn, errors="coerce").notna().mean() > 0.5:
        return 0.0
    return float(pd.to_datetime(nn.head(500), errors="coerce", format="mixed").notna().mean())


def _number_parse_rate(s: pd.Series) -> float:
    nn = s.dropna().astype(str).str.replace(",", "", regex=False).str.strip()
    return float(pd.to_numeric(nn, errors="coerce").notna().mean()) if len(nn) else 0.0


def count_affected(df: pd.DataFrame, fix: dict) -> int:
    op, col = fix["op"], fix.get("column")
    if op == "remove_duplicates":
        return int(df.duplicated().sum())
    if col not in df.columns:
        return 0
    s = df[col]
    if op in ("fill_missing", "drop_missing_rows"):
        return int(s.isna().sum())
    if op == "convert_type":
        return int(s.notna().sum())
    if op == "remove_invalid":
        return int((s < 0).sum()) if _is_num(s) else 0
    return 0


def validate_fix(df: pd.DataFrame, fix: dict) -> str | None:
    """Return an error string if the fix cannot be applied to this dataframe, else None."""
    op, col = fix.get("op"), fix.get("column")
    if op == "remove_duplicates":
        return None
    if col not in df.columns:
        return f"column '{col}' does not exist"
    s = df[col]
    if op == "fill_missing":
        strat = fix.get("strategy")
        if strat is None:
            return "fill_missing needs a strategy"
        if strat in ("median", "mean", "zero") and not _is_num(s):
            return f"strategy '{strat}' needs a numeric column"
    elif op == "convert_type":
        if fix.get("target_type") not in ("date", "number") or not _is_text(s):
            return "convert_type needs a text column and a target type of date or number"
    elif op == "remove_invalid":
        if not _is_num(s):
            return "remove_invalid needs a numeric column"
    return None


def detect_candidate_fixes(df: pd.DataFrame, profile: dict | None = None) -> list[dict]:
    """Deterministic list of problems found, each phrased as a fix from the allowed menu."""
    profile = profile or profile_dataframe(df)
    out: list[dict] = []
    if profile["duplicate_rows"] > 0:
        out.append({"op": "remove_duplicates", "column": None,
                    "reason": "Identical rows were recorded more than once and would double-count results."})
    for info in profile["columns"]:
        c = info["name"]
        s = df[c]
        if _is_text(s):
            if _date_parse_rate(s) >= 0.9:
                out.append({"op": "convert_type", "column": c, "target_type": "date",
                            "reason": f"{c} is stored as text, which prevents monthly or quarterly analysis."})
                continue
            if _number_parse_rate(s) >= 0.9:
                out.append({"op": "convert_type", "column": c, "target_type": "number",
                            "reason": f"{c} holds numbers stored as text, so it cannot be summed."})
                continue
        if _is_num(s) and NON_NEGATIVE.search(c) and (s < 0).any():
            out.append({"op": "remove_invalid", "column": c,
                        "reason": f"{c} should never be negative; these rows look like entry errors."})
        if info["missing"] > 0:
            if _is_num(s):
                if KEY_MEASURE.search(c):
                    out.append({"op": "drop_missing_rows", "column": c,
                                "reason": f"{c} is a key figure; missing values cannot be guessed safely."})
                else:
                    strat = "zero" if re.search(r"discount|bonus|fee", c, re.I) else "median"
                    out.append({"op": "fill_missing", "column": c, "strategy": strat,
                                "reason": f"{c} has {info['missing']} missing values; "
                                          f"filling with {'0' if strat == 'zero' else 'the median'} keeps those rows usable."})
            else:
                out.append({"op": "fill_missing", "column": c, "strategy": "mode" if info["missing_pct"] <= 10 else "constant",
                            "reason": f"{c} has missing values that would be dropped from group-by results."})
    return out


def finalise_fixes(df: pd.DataFrame, fixes: list[dict]) -> list[dict]:
    """Validate, de-duplicate, measure (rows affected), order and number a list of proposed fixes."""
    seen, clean = set(), []
    for f in fixes:
        if validate_fix(df, f) is not None:
            continue
        key = (f["op"], f.get("column"), f.get("target_type"))
        if key in seen:
            continue
        n = count_affected(df, f)
        if n == 0:
            continue
        seen.add(key)
        item = {k: v for k, v in f.items() if v is not None}
        item["affected_rows"] = n
        if f["op"] == "convert_type":
            s = df[f["column"]].dropna().astype(str)
            if f["target_type"] == "date":
                bad = int(pd.to_datetime(s, errors="coerce", format="mixed").isna().sum())
            else:
                bad = int(pd.to_numeric(s.str.replace(",", "", regex=False).str.strip(), errors="coerce").isna().sum())
            item["unparseable"] = bad
        clean.append(item)
    clean.sort(key=lambda f: OP_ORDER[f["op"]])
    for i, f in enumerate(clean, 1):
        f["id"] = f"fix_{i}"
    return clean


def _describe(fix: dict) -> str:
    op, col = fix["op"], fix.get("column")
    return {
        "remove_duplicates": "Removed duplicate rows",
        "fill_missing": f"Filled missing values in {col} ({fix.get('strategy')})",
        "drop_missing_rows": f"Dropped rows with missing {col}",
        "convert_type": f"Converted {col} to {fix.get('target_type')}",
        "remove_invalid": f"Removed rows with negative {col}",
    }[op]


def apply_fix(df: pd.DataFrame, fix: dict) -> tuple[pd.DataFrame, dict]:
    before = len(df)
    log = {"id": fix.get("id"), "op": fix["op"], "column": fix.get("column"), "rows_before": before}
    try:
        err = validate_fix(df, fix)
        if err:
            raise ValueError(err)
        op, col = fix["op"], fix.get("column")
        if op == "remove_duplicates":
            df = df.drop_duplicates().reset_index(drop=True)
        elif op == "drop_missing_rows":
            df = df.dropna(subset=[col]).reset_index(drop=True)
        elif op == "remove_invalid":
            df = df[~(df[col] < 0)].reset_index(drop=True)
        elif op == "fill_missing":
            s, strat = df[col], fix["strategy"]
            value = {"median": lambda: s.median(), "mean": lambda: s.mean(), "mode": lambda: s.mode().iloc[0] if not s.mode().empty else "Unknown",
                     "zero": lambda: 0, "constant": lambda: 0 if _is_num(s) else "Unknown"}[strat]()
            df = df.copy()
            df[col] = s.fillna(value)
        elif op == "convert_type":
            df = df.copy()
            s = df[col]
            if fix["target_type"] == "date":
                df[col] = pd.to_datetime(s, errors="coerce", format="mixed")
            else:
                cleaned = s.where(s.isna(), s.astype(str).str.replace(",", "", regex=False).str.strip())
                df[col] = pd.to_numeric(cleaned, errors="coerce")
        log.update(status="applied", rows_after=len(df), message=_describe(fix))
    except Exception as exc:  # noqa: BLE001 - a failed fix must not stop the others
        log.update(status="failed", rows_after=before, message=f"Skipped: {_describe(fix)} could not be applied ({exc}).")
    return df, log


def apply_fixes(df: pd.DataFrame, fixes: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    logs: list[dict] = []
    for fix in sorted(fixes, key=lambda f: OP_ORDER[f["op"]]):
        df, log = apply_fix(df, fix)
        logs.append(log)
    return df, logs

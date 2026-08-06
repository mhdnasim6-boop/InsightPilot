"""Tests for KPIEngine: default generation, explicit definitions, and extensibility."""

import pandas as pd
import pytest

from backend.analysis.exceptions.errors import UnknownKPITypeError
from backend.analysis.kpis.defaults import default_kpi_definitions
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.models.kpi import KPIDefinition, KPIType


def _df() -> pd.DataFrame:
    return pd.DataFrame({"amount": [10, 20, 30, None], "region": ["East", "West", "East", "East"]})


def test_default_definitions_include_record_count_once() -> None:
    definitions = default_kpi_definitions(_df())
    record_counts = [d for d in definitions if d.kpi_type == KPIType.RECORD_COUNT]
    assert len(record_counts) == 1
    assert record_counts[0].column is None


def test_default_definitions_skip_numeric_only_kpis_for_categorical_columns() -> None:
    definitions = default_kpi_definitions(_df())
    region_kpis = {d.kpi_type for d in definitions if d.column == "region"}
    assert region_kpis == {KPIType.NULL_PERCENTAGE, KPIType.DISTINCT_COUNT}


def test_compute_with_default_definitions() -> None:
    results = KPIEngine().compute(_df())
    by_name = {result.name: result for result in results}

    assert by_name["Record Count"].value == 4
    assert by_name["amount Null Percentage"].value == 25.0
    assert by_name["amount Distinct Count"].value == 3
    assert by_name["amount Sum"].value == 60
    assert by_name["amount Average"].value == 20.0
    assert by_name["amount Mean"].value == 20.0
    assert by_name["amount Median"].value == 20.0
    assert by_name["amount Minimum"].value == 10
    assert by_name["amount Maximum"].value == 30


def test_compute_with_explicit_definitions() -> None:
    definitions = [KPIDefinition(name="Total Amount", kpi_type=KPIType.SUM, column="amount")]
    results = KPIEngine().compute(_df(), definitions)
    assert len(results) == 1
    assert results[0].value == 60


def test_compute_returns_none_for_a_missing_column() -> None:
    definitions = [KPIDefinition(name="Ghost", kpi_type=KPIType.SUM, column="does_not_exist")]
    results = KPIEngine().compute(_df(), definitions)
    assert results[0].value is None


def test_compute_raises_for_an_unregistered_kpi_type() -> None:
    engine = KPIEngine()
    engine._calculators.clear()  # simulate no calculators registered, to exercise the guard clause
    definitions = [KPIDefinition(name="X", kpi_type=KPIType.RECORD_COUNT)]
    with pytest.raises(UnknownKPITypeError):
        engine.compute(_df(), definitions)


def test_register_adds_a_custom_calculator_without_touching_the_engine() -> None:
    def revenue_calculator(dataframe: pd.DataFrame, definition: KPIDefinition) -> float:
        return float(dataframe["amount"].sum() * 2)

    engine = KPIEngine()
    engine.register(KPIType.SUM, revenue_calculator)  # override, proving the plug-in mechanism works

    result = engine.compute(_df(), [KPIDefinition(name="Doubled", kpi_type=KPIType.SUM, column="amount")])
    assert result[0].value == 120.0

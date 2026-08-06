"""Tests for SourceType, ColumnMetadata, and BusinessDataset."""

import json
from typing import Any

from backend.ingestion.models.column import ColumnMetadata
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType, source_type_for_extension
from backend.utils.time import utc_now


def _dataset(**overrides: Any) -> BusinessDataset:
    now = utc_now()
    defaults: dict[str, Any] = {
        "dataset_id": "d1",
        "dataset_name": "sales",
        "source_type": SourceType.CSV,
        "source_location": "/data/sales.csv",
        "row_count": 3,
        "column_count": 2,
        "created_at": now,
        "loaded_at": now,
    }
    defaults.update(overrides)
    return BusinessDataset(**defaults)


def test_source_type_values() -> None:
    assert {s.value for s in SourceType} == {
        "csv",
        "excel",
        "pdf",
        "powerpoint",
        "word",
        "sqlite",
        "postgresql",
        "mysql",
        "sqlserver",
        "snowflake",
        "bigquery",
        "duckdb",
        "api",
    }


def test_source_type_for_extension_maps_file_based_types() -> None:
    assert source_type_for_extension(".csv") == SourceType.CSV
    assert source_type_for_extension(".xlsx") == SourceType.EXCEL
    assert source_type_for_extension(".xls") == SourceType.EXCEL
    assert source_type_for_extension(".pdf") == SourceType.PDF
    assert source_type_for_extension(".docx") == SourceType.WORD
    assert source_type_for_extension(".pptx") == SourceType.POWERPOINT


def test_source_type_for_extension_is_case_insensitive_and_none_for_unknown() -> None:
    assert source_type_for_extension(".CSV") == SourceType.CSV
    assert source_type_for_extension(".sqlite") is None  # connection-based, not extension-mapped


def test_column_metadata_shape() -> None:
    column = ColumnMetadata(name="age", dtype="int64", non_null_count=9, null_count=1, unique_count=5)
    assert column.name == "age"
    assert column.null_count == 1


def test_business_dataset_defaults() -> None:
    dataset = _dataset()
    assert dataset.schema == {}
    assert dataset.columns == []
    assert dataset.sample_rows == []
    assert dataset.statistics == {}
    assert dataset.quality_summary == {}
    assert dataset.metadata == {}
    assert dataset.relationships == []
    assert dataset.tags == []
    assert dataset.description is None
    assert dataset.dataframe_reference is None
    assert dataset.file_size is None


def test_business_dataset_round_trips_through_json() -> None:
    dataset = _dataset(
        schema={"age": "int64", "name": "object"},
        columns=[ColumnMetadata(name="age", dtype="int64", non_null_count=3, null_count=0, unique_count=3)],
        sample_rows=[{"age": 1, "name": "a"}],
        tags=["quarterly"],
    )

    raw = dataset.model_dump_json()
    data = json.loads(raw)

    assert data["dataset_id"] == "d1"
    assert data["schema"] == {"age": "int64", "name": "object"}
    assert data["columns"][0]["name"] == "age"
    assert data["tags"] == ["quarterly"]

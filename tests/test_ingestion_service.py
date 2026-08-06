"""Integration tests for IngestionService: select loader, validate, load, extract, return BusinessDataset."""

from pathlib import Path

import pandas as pd
import pytest

from backend.ingestion.exceptions.errors import (
    DatasetValidationError,
    SourceNotImplementedError,
)
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.models.source_type import SourceType
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.services.ingestion_service import IngestionService


def _make_service() -> IngestionService:
    return IngestionService(LoaderRegistry(), DatasetValidator(), MetadataExtractor(), DataFrameStore())


def test_ingest_csv_returns_a_populated_business_dataset(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\nWest,200\n")
    service = _make_service()

    dataset = service.ingest(str(csv_file))

    assert dataset.dataset_name == "sales"
    assert dataset.source_type == SourceType.CSV
    assert dataset.row_count == 2
    assert dataset.column_count == 2
    assert set(dataset.schema) == {"region", "amount"}
    assert dataset.file_size is not None
    assert dataset.file_size > 0
    assert dataset.quality_summary["is_valid"] is True
    assert dataset.dataframe_reference == dataset.dataset_id


def test_ingest_excel_returns_a_populated_business_dataset(tmp_path: Path) -> None:
    xlsx_file = tmp_path / "inventory.xlsx"
    pd.DataFrame({"sku": ["A1", "A2"], "qty": [10, 20]}).to_excel(xlsx_file, index=False)
    service = _make_service()

    dataset = service.ingest(str(xlsx_file), dataset_name="inventory-q1", tags=["inventory"])

    assert dataset.dataset_name == "inventory-q1"
    assert dataset.source_type == SourceType.EXCEL
    assert dataset.tags == ["inventory"]
    assert dataset.row_count == 2


def test_get_dataframe_resolves_the_real_dataframe_via_reference(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\n")
    service = _make_service()

    dataset = service.ingest(str(csv_file))
    dataframe = service.get_dataframe(dataset)

    assert dataframe is not None
    assert list(dataframe.columns) == ["region", "amount"]


def test_ingest_raises_dataset_validation_error_for_unsupported_extension(tmp_path: Path) -> None:
    json_file = tmp_path / "data.json"
    json_file.write_text("{}")

    with pytest.raises(DatasetValidationError) as exc_info:
        _make_service().ingest(str(json_file))

    assert any(issue.code == "unsupported_extension" for issue in exc_info.value.detail.errors)


def test_ingest_raises_dataset_validation_error_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"

    with pytest.raises(DatasetValidationError) as exc_info:
        _make_service().ingest(str(missing))

    assert any(issue.code == "source_not_found" for issue in exc_info.value.detail.errors)


def test_ingest_raises_dataset_validation_error_for_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")

    with pytest.raises(DatasetValidationError) as exc_info:
        _make_service().ingest(str(empty_file))

    assert any(issue.code == "empty_file" for issue in exc_info.value.detail.errors)


def test_ingest_raises_dataset_validation_error_for_corrupted_excel(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.xlsx"
    bad_file.write_text("not a real xlsx file")

    with pytest.raises(DatasetValidationError) as exc_info:
        _make_service().ingest(str(bad_file))

    assert any(issue.code == "corrupted_file" for issue in exc_info.value.detail.errors)


def test_ingest_raises_source_not_implemented_for_a_recognized_placeholder_extension(tmp_path: Path) -> None:
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_text("%PDF-1.4 not a real pdf but non-empty")

    with pytest.raises(SourceNotImplementedError):
        _make_service().ingest(str(pdf_file))


def test_ingest_dataframe_returns_a_populated_business_dataset_with_no_file_involved() -> None:
    """The source-independent counterpart to ingest() — e.g. a SQL query result."""
    dataframe = pd.DataFrame({"region": ["East", "West"], "revenue": [100, 200]})
    service = _make_service()

    dataset = service.ingest_dataframe(
        dataframe,
        dataset_name="sales_from_sql",
        source_type=SourceType.POSTGRESQL,
        source_location="postgresql://db.example.com/sales",
        metadata={"sql": {"table": "sales"}},
    )

    assert dataset.dataset_name == "sales_from_sql"
    assert dataset.source_type == SourceType.POSTGRESQL
    assert dataset.source_location == "postgresql://db.example.com/sales"
    assert dataset.file_size is None
    assert dataset.row_count == 2
    assert dataset.column_count == 2
    assert set(dataset.schema) == {"region", "revenue"}
    assert dataset.metadata == {"sql": {"table": "sales"}}
    assert dataset.dataframe_reference == dataset.dataset_id


def test_ingest_dataframe_resolves_via_get_dataframe() -> None:
    dataframe = pd.DataFrame({"a": [1, 2, 3]})
    service = _make_service()

    dataset = service.ingest_dataframe(
        dataframe, dataset_name="numbers", source_type=SourceType.SQLITE, source_location="sqlite:///:memory:/t"
    )
    resolved = service.get_dataframe(dataset)

    assert resolved is not None
    assert list(resolved["a"]) == [1, 2, 3]


def test_ingest_dataframe_raises_dataset_validation_error_for_no_columns() -> None:
    with pytest.raises(DatasetValidationError) as exc_info:
        _make_service().ingest_dataframe(
            pd.DataFrame(), dataset_name="empty", source_type=SourceType.MYSQL, source_location="mysql://db/empty"
        )

    assert any(issue.code == "invalid_schema" for issue in exc_info.value.detail.errors)

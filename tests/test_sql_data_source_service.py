"""Integration tests for SQLDataSourceService against a real, temporary SQLite database."""

from pathlib import Path

from sqlalchemy import create_engine, text

from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.models.source_type import SourceType
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.services.ingestion_service import IngestionService
from backend.services.sql_data_source_service import SQLDataSourceService


def _make_service() -> tuple[SQLDataSourceService, IngestionService]:
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), MetadataExtractor(), DataFrameStore())
    return SQLDataSourceService(ConnectorRegistry(), ingestion_service), ingestion_service


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, region TEXT)"))
        connection.execute(
            text("INSERT INTO customers VALUES (1, 'Alice', 'East'), (2, 'Bob', 'West'), (3, 'Carol', 'East')")
        )
    engine.dispose()


def _config(path: Path) -> SQLConnectionConfig:
    return SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(path))


def test_validate_connection_succeeds_for_a_real_database(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    result = service.validate_connection(_config(db_path))

    assert result.is_valid is True


def test_list_tables_returns_the_real_table_names(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    tables = service.list_tables(_config(db_path))

    assert tables == ["customers"]


def test_describe_table_returns_full_structural_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    metadata = service.describe_table(_config(db_path), "customers")

    assert metadata.row_count == 3
    assert metadata.primary_key_columns == ["id"]


def test_preview_table_returns_bounded_rows_and_metadata_together(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    preview, metadata = service.preview_table(_config(db_path), "customers", limit=2)

    assert preview.row_count_previewed == 2
    assert metadata.row_count == 3  # metadata reflects the full table, not just the preview


def test_preview_query_truncates_to_the_requested_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    preview = service.preview_query(_config(db_path), "SELECT * FROM customers ORDER BY id", limit=1)

    assert preview.row_count_previewed == 1
    assert preview.rows[0]["name"] == "Alice"


def test_import_table_returns_a_business_dataset_referencing_sql(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    dataset = service.import_table(_config(db_path), "customers", dataset_name="customers_import")

    assert dataset.dataset_name == "customers_import"
    assert dataset.source_type == SourceType.SQLITE
    assert dataset.row_count == 3
    assert dataset.metadata["sql"]["database_type"] == "sqlite"
    assert dataset.metadata["sql"]["source"] == "customers"
    # never leak the config's own metadata/credentials into the dataset
    assert "password" not in str(dataset.metadata)


def test_import_table_defaults_dataset_name_to_table_name(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    dataset = service.import_table(_config(db_path), "customers")

    assert dataset.dataset_name == "customers"


def test_import_query_returns_a_business_dataset_from_the_full_result(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, _ = _make_service()

    dataset = service.import_query(
        _config(db_path), "SELECT region, COUNT(*) AS n FROM customers GROUP BY region", dataset_name="region_counts"
    )

    assert dataset.dataset_name == "region_counts"
    assert dataset.row_count == 2
    assert set(dataset.schema) == {"region", "n"}


def test_imported_dataset_dataframe_is_resolvable_like_any_other(tmp_path: Path) -> None:
    """The whole point: a SQL-imported dataset is indistinguishable from a CSV one downstream."""
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    service, ingestion_service = _make_service()

    dataset = service.import_table(_config(db_path), "customers")
    dataframe = ingestion_service.get_dataframe(dataset)

    assert dataframe is not None
    assert len(dataframe) == 3

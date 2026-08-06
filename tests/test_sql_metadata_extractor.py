"""Tests for SQLTableMetadataExtractor against a real, temporary SQLite database.

A real (if tiny) database, not a mock: ``sqlalchemy.inspect()`` is what
this class actually depends on, and a real SQLite file exercises it
exactly the way Postgres/MySQL would — the same reasoning
``test_ingestion_loaders.py`` already applies to real CSV/Excel fixtures.
"""

from pathlib import Path

from sqlalchemy import create_engine, text

from backend.datasource.sql.metadata.table_metadata_extractor import (
    SQLTableMetadataExtractor,
)


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, region TEXT)"))
        connection.execute(
            text(
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, "
                "FOREIGN KEY(customer_id) REFERENCES customers(id))"
            )
        )
        connection.execute(text("CREATE INDEX idx_orders_customer ON orders(customer_id)"))
        connection.execute(text("INSERT INTO customers VALUES (1, 'Alice', 'East'), (2, 'Bob', 'West')"))
        connection.execute(text("INSERT INTO orders VALUES (1, 1, 100.0), (2, 2, 200.0), (3, 1, 50.0)"))
    engine.dispose()


def test_extract_reports_columns_and_primary_key(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    engine = create_engine(f"sqlite:///{db_path}")

    metadata = SQLTableMetadataExtractor().extract(engine, "customers")

    assert [column.name for column in metadata.columns] == ["id", "name", "region"]
    assert metadata.primary_key_columns == ["id"]
    id_column = next(column for column in metadata.columns if column.name == "id")
    assert id_column.primary_key is True
    name_column = next(column for column in metadata.columns if column.name == "name")
    assert name_column.primary_key is False
    assert name_column.nullable is False


def test_extract_reports_foreign_keys_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    engine = create_engine(f"sqlite:///{db_path}")

    metadata = SQLTableMetadataExtractor().extract(engine, "orders")

    assert len(metadata.foreign_keys) == 1
    fk = metadata.foreign_keys[0]
    assert fk.constrained_columns == ["customer_id"]
    assert fk.referred_table == "customers"
    assert fk.referred_columns == ["id"]

    assert len(metadata.indexes) == 1
    assert metadata.indexes[0].column_names == ["customer_id"]


def test_extract_reports_row_count_and_a_positive_estimated_size(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    engine = create_engine(f"sqlite:///{db_path}")

    metadata = SQLTableMetadataExtractor().extract(engine, "orders")

    assert metadata.row_count == 3
    assert metadata.estimated_size_bytes > 0


def test_extract_on_empty_table_reports_zero_row_count_and_zero_size(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE empty_table (id INTEGER)"))
    engine.dispose()
    engine = create_engine(f"sqlite:///{db_path}")

    metadata = SQLTableMetadataExtractor().extract(engine, "empty_table")

    assert metadata.row_count == 0
    assert metadata.estimated_size_bytes == 0

"""Tests for LoaderRegistry (extension -> loader) and DataFrameStore."""

import pandas as pd
import pytest

from backend.ingestion.exceptions.errors import (
    SourceNotImplementedError,
    UnsupportedSourceError,
)
from backend.ingestion.loaders.csv_loader import CSVLoader
from backend.ingestion.loaders.excel_loader import ExcelLoader
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry


def test_get_loader_returns_csv_loader_for_csv_extension() -> None:
    assert isinstance(LoaderRegistry().get_loader(".csv"), CSVLoader)


def test_get_loader_returns_excel_loader_for_xlsx_and_xls() -> None:
    registry = LoaderRegistry()
    assert isinstance(registry.get_loader(".xlsx"), ExcelLoader)
    assert isinstance(registry.get_loader(".xls"), ExcelLoader)


def test_get_loader_is_case_insensitive() -> None:
    assert isinstance(LoaderRegistry().get_loader(".CSV"), CSVLoader)


@pytest.mark.parametrize("extension", [".pdf", ".docx", ".pptx"])
def test_get_loader_raises_not_implemented_for_placeholder_extensions(extension: str) -> None:
    with pytest.raises(SourceNotImplementedError):
        LoaderRegistry().get_loader(extension)


def test_get_loader_raises_unsupported_for_unknown_extension() -> None:
    with pytest.raises(UnsupportedSourceError):
        LoaderRegistry().get_loader(".json")


def test_known_extensions_includes_implemented_and_placeholder() -> None:
    known = LoaderRegistry().known_extensions()
    assert {".csv", ".xlsx", ".xls", ".pdf", ".docx", ".pptx"} <= known


def test_available_extensions_only_lists_implemented() -> None:
    assert LoaderRegistry().available_extensions() == [".csv", ".xls", ".xlsx"]


def test_dataframe_store_put_get_delete() -> None:
    store = DataFrameStore()
    df = pd.DataFrame({"a": [1]})

    assert store.get("d1") is None

    store.put("d1", df)
    retrieved = store.get("d1")
    assert retrieved is not None
    assert retrieved.equals(df)

    assert store.delete("d1") is True
    assert store.get("d1") is None
    assert store.delete("d1") is False

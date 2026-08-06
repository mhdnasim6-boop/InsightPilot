"""Tests for CSVLoader and ExcelLoader: loading only, no cleaning/transformation."""

from pathlib import Path

import pandas as pd
import pytest

from backend.ingestion.exceptions.errors import DatasetCorruptedError
from backend.ingestion.loaders.csv_loader import CSVLoader
from backend.ingestion.loaders.excel_loader import ExcelLoader


def test_csv_loader_supported_extensions() -> None:
    assert CSVLoader().supported_extensions() == frozenset({".csv"})


def test_csv_loader_loads_a_real_file(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b\n1,x\n2,y\n")

    df = CSVLoader().load(str(csv_file))

    assert list(df.columns) == ["a", "b"]
    assert df.shape == (2, 2)


def test_csv_loader_raises_dataset_corrupted_on_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")

    with pytest.raises(DatasetCorruptedError):
        CSVLoader().load(str(empty_file))


def test_csv_loader_validate_and_metadata_defaults(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b\n1,2\n")
    loader = CSVLoader()

    result = loader.validate(str(csv_file))

    assert result.is_valid is True
    assert loader.metadata() == {"name": "CSVLoader", "supported_extensions": [".csv"]}


def test_excel_loader_supported_extensions() -> None:
    assert ExcelLoader().supported_extensions() == frozenset({".xlsx", ".xls"})


def test_excel_loader_loads_a_real_file(tmp_path: Path) -> None:
    xlsx_file = tmp_path / "data.xlsx"
    pd.DataFrame({"x": [1, 2], "y": ["a", "b"]}).to_excel(xlsx_file, index=False)

    df = ExcelLoader().load(str(xlsx_file))

    assert list(df.columns) == ["x", "y"]
    assert df.shape == (2, 2)


def test_excel_loader_raises_dataset_corrupted_on_bad_file(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.xlsx"
    bad_file.write_text("not a real xlsx file")

    with pytest.raises(DatasetCorruptedError):
        ExcelLoader().load(str(bad_file))

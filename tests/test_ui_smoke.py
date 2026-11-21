"""Streamlit pages render without errors (no LLM call is made by these pages on load)."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
PAGES = ["app/Home.py", "app/pages/1_Dashboard.py", "app/pages/2_Data.py", "app/pages/3_Copilot.py"]


@pytest.fixture
def ui_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INSIGHTPILOT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    import ui_common
    ui_common.get_app.clear()
    yield ui_common
    ui_common.get_app.clear()


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_without_data(ui_env, page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=30).run()
    assert not at.exception, at.exception


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_with_sample_data(ui_env, page):
    app = ui_env.get_app()
    ds = app.upload_dataset("sales.csv", (ROOT / "sample_data" / "sales.csv").read_bytes())
    at = AppTest.from_file(str(ROOT / page), default_timeout=30)
    at.session_state["dataset_id"] = ds
    at.run()
    assert not at.exception, at.exception


def test_home_loads_sample_button(ui_env):
    at = AppTest.from_file(str(ROOT / "app/Home.py"), default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["dataset_id"]

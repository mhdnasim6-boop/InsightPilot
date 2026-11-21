import pytest
from langchain_core.messages import AIMessage

from insightpilot.config import Settings
from insightpilot.data.sample import generate_sales
from insightpilot.data.store import DatasetStore
from insightpilot.providers.mock_provider import MockProvider
from insightpilot.runtime import InsightPilotApp
from insightpilot.schemas import RoutingDecision


@pytest.fixture
def settings(tmp_path):
    return Settings.from_env().with_overrides(data_dir=str(tmp_path / "data"), tavily_api_key="", smtp_host="")


@pytest.fixture
def store(settings):
    return DatasetStore(settings)


@pytest.fixture
def sales_df():
    df, planted = generate_sales(n_rows=600, seed=7, with_issues=True)
    return df


@pytest.fixture
def clean_sales_df():
    df, _ = generate_sales(n_rows=600, seed=7, with_issues=False)
    return df


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def app(settings, store, provider):
    a = InsightPilotApp(settings=settings, provider=provider, store=store)
    yield a
    a.close()


def route(agent, reason="test", reply=None):
    return RoutingDecision(next_agent=agent, reason=reason, direct_reply=reply)


def sql_call(sql, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": "run_sql", "args": {"sql": sql}, "id": call_id}])

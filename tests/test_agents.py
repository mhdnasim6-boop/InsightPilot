"""Agent-level behaviour: supervisor rules, analyst retry limits, research, visualization, memory, tools."""
import json

import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage

from insightpilot.agents.analyst import make_data_analyst
from insightpilot.agents.research import make_research
from insightpilot.agents.supervisor import make_supervisor
from insightpilot.agents.visualization import make_visualization
from insightpilot.graph.memory import build_context, maybe_summarize
from insightpilot.providers.mock_provider import MockProvider
from insightpilot.schemas import ChartSpec
from insightpilot.tools.chart_tool import build_chart, default_chart_spec, validate_chart_spec
from insightpilot.tools.email_tool import find_email, send_email, valid_email
from insightpilot.tools.report_tool import generate_report_pdf
from insightpilot.tools.search_tool import make_search_tool
from tests.conftest import route, sql_call

COLS, ROWS = ["region", "total"], [["North", 10.0], ["South", 5.0], ["East", 7.0]]


def _state(**kw):
    base = {"messages": [HumanMessage(content="q")], "dataset_id": "d", "dataset_cleaned": True, "agents_run": [], "step_count": 0}
    return {**base, **kw}


# ---- supervisor -----------------------------------------------------------------------------
def test_supervisor_rule_no_dataset(settings):
    out = make_supervisor(MockProvider(), settings)(_state(dataset_id=""))
    assert out["next_agent"] == "FINISH" and "upload" in out["final_answer"].lower()


def test_supervisor_rule_cleans_first_without_llm(settings):
    p = MockProvider()
    out = make_supervisor(p, settings)(_state(dataset_cleaned=False))
    assert out["next_agent"] == "data_cleaning" and p.log == []


def test_supervisor_step_limit(settings):
    out = make_supervisor(MockProvider(), settings)(_state(step_count=settings.max_supervisor_steps))
    assert out["next_agent"] == "FINISH"


def test_supervisor_cannot_repeat_or_skip_analysis(settings):
    p = MockProvider().script_structured("RoutingDecision", route("report_email"), route("data_analyst"))
    sup = make_supervisor(p, settings)
    assert sup(_state())["next_agent"] == "data_analyst"                       # report needs analysis first
    out = sup(_state(agents_run=["data_analyst"], analysis_result={"rows": [1]}))
    assert out["next_agent"] == "FINISH"                                        # data_analyst already ran


def test_supervisor_survives_bad_llm_output(settings):
    out = make_supervisor(MockProvider(), settings)(_state())                   # nothing scripted -> StructuredOutputError
    assert out["next_agent"] == "FINISH" and out["final_answer"] and out["errors"]


# ---- analyst --------------------------------------------------------------------------------
def test_analyst_recovers_from_bad_sql(settings, store, clean_sales_df):
    ds = store.create_from_dataframe("s.csv", clean_sales_df)
    p = MockProvider().script_model(sql_call("SELECT nope FROM data", "a"), sql_call("SELECT COUNT(*) AS n FROM data", "b"), AIMessage(content="Counted."))
    out = make_data_analyst(p, store, settings)(_state(dataset_id=ds))
    assert out["analysis_result"]["rows"][0][0] == len(clean_sales_df)


def test_analyst_stops_after_max_failures(settings, store, clean_sales_df):
    ds = store.create_from_dataframe("s.csv", clean_sales_df)
    bad = [sql_call("SELECT nope FROM data", f"c{i}") for i in range(10)]
    p = MockProvider().script_model(*bad)
    out = make_data_analyst(p, store, settings)(_state(dataset_id=ds))
    assert "analysis_result" not in out and out["errors"]
    assert len(p.chat_model.calls) == settings.max_sql_retries              # bounded, no endless loop


def test_analyst_rejects_destructive_sql(settings, store, clean_sales_df):
    ds = store.create_from_dataframe("s.csv", clean_sales_df)
    p = MockProvider().script_model(sql_call("DROP TABLE data", "a"), sql_call("SELECT 1 AS one", "b"), AIMessage(content="ok"))
    out = make_data_analyst(p, store, settings)(_state(dataset_id=ds))
    assert out["analysis_result"]["rows"] == [[1]] and len(store.load_df(ds)) == len(clean_sales_df)


# ---- research ---------------------------------------------------------------------------------
def test_research_skips_without_key(settings):
    out = make_research(MockProvider(), settings)(_state())
    assert "TAVILY_API_KEY" in out["research_note"] and out["external_evidence"] == []


def test_research_collects_sourced_evidence(settings):
    hits = [{"title": "Port strike", "url": "https://news.example.com/a", "publisher": "example", "published_date": "2025-03-02", "snippet": "s"}]
    p = MockProvider().script_model(
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "q"}, "id": "t1"}]),
        AIMessage(content="A port strike may be related."))
    out = make_research(p, settings, search_fn=lambda q: hits)(_state(analysis_result={"columns": COLS, "rows": ROWS}))
    assert out["external_evidence"][0]["url"] == "https://news.example.com/a" and "may be related" in out["research_note"]


def test_search_tool_retries_then_reports_failure(settings):
    calls = []

    def flaky(q):
        calls.append(q)
        raise RuntimeError("boom")
    res = json.loads(make_search_tool(settings, flaky).invoke({"query": "x"}))
    assert res["ok"] is False and len(calls) == 2


# ---- visualization -----------------------------------------------------------------------------
def test_visualization_uses_llm_choice_when_valid():
    p = MockProvider().script_structured("ChartSpec", ChartSpec(chart_type="bar", x="region", y="total", title="T"))
    out = make_visualization(p)(_state(analysis_result={"columns": COLS, "rows": ROWS, "question": "q"}))
    assert out["chart_spec"]["title"] == "T" and out["visualization"]


def test_visualization_falls_back_on_invalid_choice():
    p = MockProvider().script_structured("ChartSpec", ChartSpec(chart_type="bar", x="ghost", y="total", title="T"))
    out = make_visualization(p)(_state(analysis_result={"columns": COLS, "rows": ROWS, "question": "q"}))
    assert out["chart_spec"]["x"] == "region"


def test_visualization_skips_single_value():
    out = make_visualization(MockProvider())(_state(analysis_result={"columns": ["n"], "rows": [[5]]}))
    assert "visualization" not in out


def test_chart_validation_rules():
    assert validate_chart_spec({"chart_type": "pie", "x": "region", "y": "total"}, COLS, ROWS)
    assert validate_chart_spec({"chart_type": "grouped_bar", "x": "region", "y": "total"}, COLS, ROWS) is None
    assert validate_chart_spec({"chart_type": "bar", "x": "region", "y": "region"}, COLS, ROWS) is None
    assert build_chart(default_chart_spec(COLS, ROWS), COLS, ROWS).data


# ---- memory ---------------------------------------------------------------------------------------
def test_context_is_trimmed_to_budget(settings):
    msgs = []
    for i in range(60):
        msgs += [HumanMessage(content=f"question {i} " + "x" * 400), AIMessage(content=f"answer {i} " + "y" * 400)]
    ctx = build_context({"messages": msgs + [HumanMessage(content="latest?")]}, settings)
    assert len(ctx) < len(msgs) and ctx[-1].content == "latest?"


def test_summary_created_when_history_long(settings):
    msgs = []
    for i in range(20):
        msgs += [HumanMessage(content=f"q{i}"), AIMessage(content=f"a{i}")]
    p = MockProvider().script_chat("User asked about revenue.")
    out = maybe_summarize(p, {"messages": msgs}, settings)
    assert out["conversation_summary"] and out["summarized_upto"] == len(msgs) - settings.keep_recent_messages
    ctx = build_context({"messages": msgs, **out}, settings)
    assert "Summary" in ctx[0].content


# ---- email / report -----------------------------------------------------------------------------
def test_email_helpers_and_outbox(settings, tmp_path):
    assert valid_email("a@b.co") and not valid_email("nope") and find_email("send to x@y.com please") == "x@y.com"
    assert send_email("bad", "s", "b", None, settings)["status"] == "failed"
    out = send_email("a@b.co", "s", "b", None, settings)
    assert out["status"] == "saved_to_outbox" and out["detail"].endswith(".eml")


def test_pdf_report_created(tmp_path):
    f = generate_report_pdf(tmp_path / "r.pdf", title="T", dataset_name="d", executive_summary="s", key_findings=["f"],
                            columns=COLS, rows=ROWS, sql="SELECT 1", evidence=[], limitations="l")
    assert f.read_bytes()[:4] == b"%PDF"

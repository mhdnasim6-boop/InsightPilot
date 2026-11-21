"""End-to-end graph tests with a scripted provider: routing, both approvals, memory, error handling."""
from pathlib import Path

from langchain_core.messages import AIMessage

from tests.conftest import route, sql_call

SQL = "SELECT region, SUM(revenue) AS total_revenue FROM data GROUP BY region ORDER BY total_revenue DESC"


def test_chat_with_cleaning_approval_then_analysis(app, provider, sales_df):
    ds = app.store.create_from_dataframe("sales.csv", sales_df)
    tid = app.new_conversation(ds)
    r = app.ask(tid, ds, "Which region has the highest revenue?")
    assert r["status"] == "interrupted" and r["interrupt"]["type"] == "cleaning_fixes"
    fixes = r["interrupt"]["fixes"]
    assert {f["op"] for f in fixes} >= {"remove_duplicates"}
    rows_before = len(app.store.load_df(ds))            # nothing changed before approval
    provider.script_structured("RoutingDecision", route("data_analyst"), route("visualization"), route("FINISH"))
    provider.script_model(sql_call(SQL), AIMessage(content="Revenue by region."))
    provider.script_chat("North leads on revenue.")
    r = app.resume(tid, {"approved_ids": [f["id"] for f in fixes]})
    assert r["status"] == "done", r
    assert len(app.store.load_df(ds)) < rows_before
    assert "North" in r["answer"] or "leads" in r["answer"]
    assert r["visualization"]                           # chart produced
    assert [a["agent"] for a in r["audit"] if a["agent"] != "supervisor"][:3] == ["data_cleaning", "cleaning_approval", "data_analyst"]


def test_rejecting_cleaning_leaves_data_unchanged(app, provider, sales_df):
    ds = app.store.create_from_dataframe("sales.csv", sales_df)
    tid = app.new_conversation(ds)
    app.ask(tid, ds, "total revenue?")
    n = len(app.store.load_df(ds))
    provider.script_structured("RoutingDecision", route("FINISH", reply="ok"))
    r = app.resume(tid, {"approved_ids": []})
    assert r["status"] == "done" and len(app.store.load_df(ds)) == n


def test_greeting_needs_no_specialist(app, provider, clean_sales_df):
    ds = app.store.create_from_dataframe("s.csv", clean_sales_df)
    tid = app.new_conversation(ds)
    app.store.update_meta(ds, cleaned=True)
    provider.script_structured("RoutingDecision", route("FINISH", reply="Hello! Ask me about your data."))
    r = app.ask(tid, ds, "hi")
    assert r["status"] == "done" and r["answer"].startswith("Hello")


def test_email_requires_approval_and_is_not_sent_before(app, provider, clean_sales_df, settings):
    ds = app.store.create_from_dataframe("s.csv", clean_sales_df)
    app.store.update_meta(ds, cleaned=True)
    tid = app.new_conversation(ds)
    provider.script_structured("RoutingDecision", route("data_analyst"), route("report_email"))
    provider.script_model(sql_call(SQL), AIMessage(content="done"))
    r = app.ask(tid, ds, "Make a report on revenue by region and email it to boss@example.com")
    assert r["status"] == "interrupted" and r["interrupt"]["type"] == "send_email"
    assert r["interrupt"]["draft"]["to"] == "boss@example.com"
    assert not (Path(settings.data_dir) / "outbox").exists()       # nothing sent before approval
    provider.script_chat("Report ready.")
    r = app.resume(tid, {"approved": True})
    assert r["status"] == "done" and r["email_status"] == "saved_to_outbox"
    assert r["report"]["path"].endswith(".pdf")


def test_email_rejected_is_not_sent(app, provider, clean_sales_df):
    ds = app.store.create_from_dataframe("s.csv", clean_sales_df)
    app.store.update_meta(ds, cleaned=True)
    tid = app.new_conversation(ds)
    provider.script_structured("RoutingDecision", route("data_analyst"), route("report_email"))
    provider.script_model(sql_call(SQL), AIMessage(content="done"))
    app.ask(tid, ds, "report on revenue by region, email to a@b.com")
    provider.script_chat("ok")
    r = app.resume(tid, {"approved": False})
    assert r["email_status"] == "rejected"


def test_email_without_recipient_asks_for_one(app, provider, clean_sales_df):
    ds = app.store.create_from_dataframe("s.csv", clean_sales_df)
    app.store.update_meta(ds, cleaned=True)
    tid = app.new_conversation(ds)
    provider.script_structured("RoutingDecision", route("data_analyst"), route("report_email"))
    provider.script_model(sql_call(SQL), AIMessage(content="done"))
    provider.script_chat("Report made.")
    r = app.ask(tid, ds, "make a report and email it")
    assert r["status"] == "done" and r["email_status"] == "needs_recipient"
    assert "email address" in r["answer"]


def test_memory_persists_across_turns(app, provider, clean_sales_df):
    ds = app.store.create_from_dataframe("s.csv", clean_sales_df)
    app.store.update_meta(ds, cleaned=True)
    tid = app.new_conversation(ds)
    provider.script_structured("RoutingDecision", route("FINISH", reply="First answer."), route("FINISH", reply="Second answer."))
    app.ask(tid, ds, "hello")
    app.ask(tid, ds, "and now?")
    hist = app.history(tid)
    assert [h["role"] for h in hist] == ["user", "assistant", "user", "assistant"]


def test_unavailable_provider_gives_friendly_error(app, provider, clean_sales_df):
    from insightpilot.providers.base import ProviderUnavailable
    ds = app.store.create_from_dataframe("s.csv", clean_sales_df)
    app.store.update_meta(ds, cleaned=True)
    tid = app.new_conversation(ds)
    provider.script_structured("RoutingDecision", ProviderUnavailable("down"))
    provider.name = "ollama"
    r = app.ask(tid, ds, "hi")
    assert r["status"] == "error" and "Ollama" in r["error"] and "Traceback" not in r["error"]

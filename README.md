# InsightPilot - Agentic AI Business Intelligence Platform

Upload business data, let a team of AI agents clean it (with your approval), then ask questions in plain English.
Every number is calculated by a SQL engine (DuckDB); the LLM only decides *what to ask* and *how to explain it*.

See `docs/workflow.txt` for the graph.

## What it does

| Agent | Type | Job |
|---|---|---|
| **Supervisor** | custom (LangGraph node + structured output) | Decides which specialist runs next, or finishes |
| **Data Cleaning** | custom | Finds duplicates, missing/invalid values, text dates; proposes fixes |
| **Data Analyst** | custom (tool loop) | Writes read-only SQL, runs it in DuckDB, retries on errors |
| **Visualization** | custom | Chooses a chart for the result; Plotly draws it |
| **Research** | **existing** prebuilt ReAct agent (`langchain.agents.create_agent`) + Tavily web search | Finds possible external context for a change |
| **Report & Email** | custom | Builds a PDF report, drafts an email |

**Two Human-in-the-Loop approvals** (real LangGraph `interrupt()`, state checkpointed to SQLite):
1. Data-cleaning fixes - nothing in the data changes until you approve (per-fix checkboxes).
2. Sending an email - the draft is editable and is only sent after you press *Approve*.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit (see below)
streamlit run app/Home.py
```
Open **Home -> Load sample sales data**, then **Data -> Check data quality**, then **Copilot**.

### Local model (Ollama + Qwen2.5:3B)
```bash
ollama pull qwen2.5:3b
# .env:  LLM_PROVIDER=ollama
```
### Cloud model (OpenAI)
```
# .env:  LLM_PROVIDER=openai   OPENAI_API_KEY=sk-...   OPENAI_MODEL=gpt-4o-mini
```
That single `.env` line is the whole switch; restart the app. All agents talk to the `AIProvider` interface
(`insightpilot/providers/base.py`); `OllamaProvider` and `OpenAIProvider` implement it. Adding a vendor = one new class + one line in `factory.py`.

Optional: `TAVILY_API_KEY` enables the Research agent (without it the step is skipped with a clear note);
`SMTP_*` enables real sending (without it approved emails are saved as `.eml` files in `data/outbox/`);
`LANGSMITH_*` enables tracing.

## Demo paths (sample data has planted issues and a planted story)

1. **Human-in-the-loop cleaning** - Data page -> *Check data quality*. The agent finds 39 duplicates, 39 missing discounts, 5 negative quantities and text dates. Untick one fix, apply, see the change log.
2. **Analytics** - Copilot: *Which region has the highest revenue?* -> SQL, table, chart.
3. **Multi-agent investigation** - *Why did North electronics revenue drop in March 2025?* -> Analyst measures the drop, Research adds sourced "may be related" context.
4. **Memory** - follow up with *and what about South?* (the Copilot resolves it from the conversation).
5. **Report + approved email** - *Make a report on revenue by region and email it to name@company.com* -> approve/edit the draft.

## Resume claim -> where it lives in the code

| Claim | Evidence |
|---|---|
| LangGraph-orchestrated agents | `insightpilot/graph/workflow.py` (StateGraph, supervisor loop, conditional edges, subgraphs) |
| Vendor-agnostic `AIProvider` interface | `providers/base.py`, `ollama_provider.py`, `openai_provider.py`, `factory.py`; test: `tests/test_providers.py` |
| Intelligent automated business analytics | `agents/analyst.py`, `data/store.py` (DuckDB), `data/kpis.py`, `agents/report_email.py` |
| Enterprise-scale | Benchmarked only at the SQL layer: 1M rows, all queries < 0.15 s (`benchmarks/results.md`). See limitations |
| Context-aware Copilot with conversation memory | `graph/memory.py` (summary + token-trimmed window), SQLite checkpointer per `thread_id` (`runtime.py`); test: `test_memory_persists_across_turns` |
| Human-in-the-Loop approval | `agents/cleaning.py::cleaning_approval`, `agents/report_email.py::email_approval`; tests in `tests/test_e2e_workflow.py` |
| Local (Ollama Qwen2.5:3B) / cloud (OpenAI) switching | `LLM_PROVIDER` in `.env` -> `providers/factory.py` |

## Design decisions worth knowing

- **The LLM never does arithmetic.** It writes SQL; DuckDB computes. SQL is validated SELECT-only (`data/sql_guard.py`) *and* run on a locked-down connection (no file/network access, config locked, one connection per query, row limit, timeout).
- **LLM decides, code enforces.** Routing, cleaning fixes and chart choices are Pydantic-validated objects restricted to fixed menus (`schemas.py`). The supervisor's choices are checked in code (no repeats, no report before analysis); a failed or invalid LLM output falls back to rule-based behaviour.
- **Bounded loops.** Supervisor steps, SQL retries, research cycles and graph recursion all have limits (`config.py`).
- **Small-model friendly.** Short prompts, enum outputs, token-trimmed context, rolling summary.
- **Honest failure.** Ollama not running, missing API key, search down, bad SQL -> friendly message, never a traceback.

## Tests and benchmark

```bash
pytest -q                                   # 70+ tests, no network and no LLM needed (scripted MockProvider)
python benchmarks/run_benchmark.py          # DuckDB timings at 100K and 1M rows -> benchmarks/results.md
```

## Honest limitations

- Tests use a scripted provider, so they verify the **orchestration** (routing, approvals, memory, retries, safety), not the **quality** of any real model's answers. A 3B local model will be weaker than GPT-4o-mini at SQL and routing; the guards and fallbacks exist for that reason, but expect more "rephrase your question" replies locally.
- The benchmark measures DuckDB, not end-to-end latency with an LLM. "Enterprise-scale" here means "the analytics layer handles millions of rows quickly", not multi-user deployment, auth or access control.
- The cleaning menu is fixed (duplicates, missing values, text->date/number, invalid negatives); it is not a general data-wrangling tool.
- "Why" answers are correlational: external news is shown as *possibly related*, never as the cause.
- Single-user, local-file storage (parquet + SQLite). No authentication.
- Provider parity was designed for (same interface, structured-output fallbacks) but a given feature may behave differently across models.

## Layout

```
app/            Streamlit UI (Home, Dashboard, Data, Copilot)
insightpilot/   providers/  agents/  tools/  data/  graph/  runtime.py  config.py  schemas.py
tests/          unit + end-to-end graph tests + UI smoke tests
benchmarks/     DuckDB benchmark and results
sample_data/    sales.csv (planted issues) - regenerate with scripts/make_sample_data.py
```

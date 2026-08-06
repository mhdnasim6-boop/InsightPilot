"""Planning page: the home for turning a request into work — a persisted,
reusable Workflow built from an objective or explicit steps; a one-off Quick
Action run directly against a single dataset/database/research topic; or a
draft Plan you preview/validate/edit before running it. Track a run's live
progress and approvals on the Execution page.

This page absorbs the old Planning page's own unique capability (Phase v1.0
navigation redesign: Quick Actions, Draft-a-Plan preview/validate/edit/
approval-policy/history) alongside the Workflow Engine's own builder/list/
detail view that already lived here — nothing was removed, only
reorganized into tabs instead of one long scroll, and every button/label
that used to name a backend agent class directly (``FileAgent``,
``SQLAgent``, ``BrowserAgent``, ...) now describes the task instead.
"""

import json
from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import (
    render_api_error,
    render_dataset_info,
    render_execution_plan,
    render_kpi_cards,
)
from frontend.layouts import ensure_session, page_header, render_sidebar
from frontend.state import get_dashboard_state

_STATUS_ICONS = {
    "draft": "⚪", "validated": "🔵", "optimized": "🔵", "ready": "🔵",
    "running": "🟡", "paused": "🟠", "completed": "🟢", "failed": "🔴", "cancelled": "⚫",
}
_SQL_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}
_PIPELINE_STAGES = [
    ("Ingestion", "dataset"), ("Cleaning", "cleaning"), ("Analysis", "analysis"),
    ("Visualization", "visualization"), ("Report", "report"),
]
_APPROVAL_POLICY_OPTIONS = ["never", "always", "on_risky_operations", "on_sql", "on_browser", "on_report_publishing"]
_APPROVAL_POLICY_LABELS = {
    "never": "Never require approval", "always": "Always require approval",
    "on_risky_operations": "Only for risky operations", "on_sql": "Only before database actions",
    "on_browser": "Only before web research", "on_report_publishing": "Only before publishing a report",
}


def _status_label(status: str) -> str:
    return f"{_STATUS_ICONS.get(status, '')} {status}"


def _authenticated_client(state: Any) -> APIClient:
    return APIClient(state.backend_url, access_token=state.access_token)


# -- Approval policy (cross-cutting: applies to Quick Actions, Draft-a-Plan, and Workflows) ----


def _render_approval_policy(client: APIClient) -> None:
    with st.expander("Approval settings"):
        st.caption("Optionally require a human to approve a step before it runs.")
        try:
            active_policy = client.get_approval_policy()["policy_type"]
        except APIClientError:
            active_policy = "never"
        chosen_policy = st.selectbox(
            "Require approval before a step runs",
            _APPROVAL_POLICY_OPTIONS,
            index=_APPROVAL_POLICY_OPTIONS.index(active_policy) if active_policy in _APPROVAL_POLICY_OPTIONS else 0,
            format_func=lambda value: _APPROVAL_POLICY_LABELS.get(value, value),
        )
        if chosen_policy != active_policy and st.button("Apply"):
            try:
                client.set_approval_policy(chosen_policy)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                st.success(f"Approval setting updated to '{_APPROVAL_POLICY_LABELS.get(chosen_policy, chosen_policy)}'.")
                st.rerun()


# -- Quick Actions (migrated from the old Planning page's direct agent controls) ---------------


def _render_quick_file_analysis(state: Any, client: APIClient, session_id: str | None) -> None:
    st.markdown("**Quick File Analysis**")
    st.caption("Ingests, cleans, analyzes, and visualizes one file end to end — optionally generating a report too.")

    default_reference = ""
    if state.selected_dataset:
        default_reference = state.selected_dataset.get("source_location") or ""

    dataset_reference = st.text_input("File path", value=default_reference, key="quick_file_reference")
    generate_report = st.checkbox("Also generate a report", value=False, key="quick_file_generate_report")

    if st.button("Run File Analysis", type="primary", disabled=not dataset_reference.strip(), key="quick_file_run"):
        if session_id is None:
            render_api_error(APIClientError("No active session and the backend is unreachable."))
            return
        result: dict[str, Any] | None
        with st.spinner("Analyzing file..."):
            try:
                result = client.execute_file_agent(dataset_reference.strip(), session_id, generate_report)
            except APIClientError as exc:
                render_api_error(exc)
                result = None
        if result is not None:
            state.current_agent_execution = result
            verb = "completed" if result["status"] == "completed" else "failed"
            state.add_activity(f"Quick file analysis {verb} for '{dataset_reference}'.")

    try:
        executions = client.list_file_agent_executions()
    except APIClientError as exc:
        render_api_error(exc)
        executions = []
    if executions:
        with st.expander(f"Previous file analysis runs ({len(executions)})"):
            options = {f"{e['step_id']} — {e['status']}": e for e in executions}
            chosen_label = st.selectbox("Load a previous run", list(options.keys()), key="quick_file_history_pick")
            if st.button("Load selected run", key="quick_file_history_load"):
                state.current_agent_execution = options[chosen_label]


def _render_quick_database_query(state: Any, client: APIClient, session_id: str | None) -> None:
    st.markdown("**Quick Database Query**")
    st.caption("Imports a table or a custom query, then cleans, analyzes, and visualizes it — optionally generating a report too.")

    col1, col2 = st.columns(2)
    database_type = col1.selectbox("Database type", ["sqlite", "postgresql", "mysql"], key="quick_sql_db_type")
    if database_type == "sqlite":
        database = col2.text_input("Database file path", key="quick_sql_database")
        host = username = password = None
        port = None
    else:
        database = col2.text_input("Database name", key="quick_sql_database")
        col3, col4 = st.columns(2)
        host = col3.text_input("Host", key="quick_sql_host")
        port = col4.number_input(
            "Port", min_value=1, max_value=65535, value=_SQL_DEFAULT_PORTS.get(database_type), step=1, key="quick_sql_port",
        )
        col5, col6 = st.columns(2)
        username = col5.text_input("Username", key="quick_sql_username")
        password = col6.text_input("Password", type="password", key="quick_sql_password")

    target_mode = st.radio("Import from", ["Table", "Query"], horizontal=True, key="quick_sql_target_mode")
    if target_mode == "Table":
        table_name = st.text_input("Table name", key="quick_sql_table_name")
        query = None
    else:
        query = st.text_area("SQL query", key="quick_sql_query")
        table_name = None

    generate_report = st.checkbox("Also generate a report", value=False, key="quick_sql_generate_report")

    if st.button("Run Database Query", type="primary", disabled=not database or not (table_name or query), key="quick_sql_run"):
        if session_id is None:
            render_api_error(APIClientError("No active session and the backend is unreachable."))
            return
        connection = {
            "database_type": database_type, "host": host or None, "port": int(port) if port else None,
            "database": database, "username": username or None, "password": password or None,
        }
        result: dict[str, Any] | None
        with st.spinner("Running query..."):
            try:
                result = client.execute_sql_agent(
                    connection, session_id, table_name=table_name or None, query=query or None,
                    generate_report=generate_report,
                )
            except APIClientError as exc:
                render_api_error(exc)
                result = None
        if result is not None:
            state.current_agent_execution = result
            target_label = table_name or "a custom query"
            verb = "completed" if result["status"] == "completed" else "failed"
            state.add_activity(f"Quick database query {verb} for {target_label}.")


def _render_quick_pipeline_result(result: dict[str, Any]) -> None:
    status = result["status"]
    summary = f"Run {status} in {result.get('execution_time', 0.0):.2f}s"
    (st.success if status == "completed" else st.error)(summary)
    for warning in result.get("warnings", []):
        st.warning(warning)

    cols = st.columns(len(_PIPELINE_STAGES))
    for col, (label, field) in zip(cols, _PIPELINE_STAGES, strict=False):
        col.markdown(f"{'✅' if result.get(field) is not None else '⬜'} {label}")

    if result.get("dataset"):
        st.markdown("**Dataset**")
        render_dataset_info(result["dataset"])
    if result.get("cleaning"):
        st.caption(f"Cleaning quality score: {result['cleaning']['result']['quality_score']}")
    if result.get("analysis"):
        st.markdown("**KPIs**")
        render_kpi_cards(result["analysis"]["kpis"])
    if result.get("visualization"):
        st.caption(f"{len(result['visualization']['charts'])} chart(s) generated.")
    if result.get("report"):
        st.markdown(f"**Report** — {result['report']['title']}")


def _split_topics(raw: str) -> list[str]:
    return [topic.strip() for topic in raw.split(",") if topic.strip()]


def _render_quick_web_research(state: Any, client: APIClient, session_id: str | None) -> None:
    st.markdown("**Web Research**")
    st.caption(
        "Gathers external context (never business analysis) for a topic. Every field is "
        "optional — leave everything blank and it gracefully skips."
    )

    search_request = st.text_input("Research topic (free text)", key="quick_research_request")
    col1, col2 = st.columns(2)
    companies = _split_topics(col1.text_input("Company names (comma-separated)", key="quick_research_companies"))
    industries = _split_topics(col2.text_input("Industry names (comma-separated)", key="quick_research_industries"))
    col3, col4 = st.columns(2)
    products = _split_topics(col3.text_input("Product names (comma-separated)", key="quick_research_products"))
    keywords = _split_topics(col4.text_input("Keywords (comma-separated)", key="quick_research_keywords"))
    has_any_topic = bool(search_request.strip() or companies or industries or products or keywords)

    if st.button("Run Web Research", type="primary", disabled=not has_any_topic, key="quick_research_run"):
        if session_id is None:
            render_api_error(APIClientError("No active session and the backend is unreachable."))
            return
        result: dict[str, Any] | None
        with st.spinner("Researching..."):
            try:
                result = client.execute_browser_agent(
                    session_id, search_request=search_request.strip() or None, companies=companies,
                    industries=industries, products=products, keywords=keywords,
                )
            except APIClientError as exc:
                render_api_error(exc)
                result = None
        if result is not None:
            state.current_browser_execution = result
            if result["status"] == "completed":
                state.add_activity(f"Web research completed with {len(result['sources'])} source(s).")
            elif result["status"] == "skipped":
                state.add_activity("Web research skipped: no research-relevant input given.")
            else:
                state.add_activity("Web research failed.")

    result = state.current_browser_execution
    if result is not None:
        status = result["status"]
        summary = f"Web research {status} in {result.get('execution_time', 0.0):.2f}s"
        if status == "completed":
            st.success(summary)
        elif status == "skipped":
            st.info(summary + " — no research-relevant input was given.")
        else:
            st.error(summary)
        for warning in result.get("warnings", []):
            st.warning(warning)
        for entry in result.get("summaries") or []:
            st.markdown(f"- **{entry['query']}**: {entry['summary']}")
        for source in result.get("sources") or []:
            st.markdown(f"- [{source['title']}]({source['url']}) — {source['snippet']}")


def _render_quick_report(state: Any, client: APIClient, session_id: str | None) -> None:
    pipeline_result = state.current_agent_execution
    has_dataset = bool(
        pipeline_result and pipeline_result.get("status") == "completed" and pipeline_result.get("dataset")
    )
    if not has_dataset:
        return

    st.markdown("**Generate a Report from this run**")
    try:
        template_types = client.list_report_templates()
    except APIClientError:
        template_types = ["business_report"]
    try:
        theme_names = client.list_report_themes()
    except APIClientError:
        theme_names = ["corporate"]

    col1, col2 = st.columns(2)
    template_type = col1.selectbox("Template", template_types, key="quick_report_template_type")
    theme = col2.selectbox("Theme", theme_names, key="quick_report_theme")
    title = st.text_input("Title (optional)", key="quick_report_title")

    browser_result = state.current_browser_execution
    include_research = False
    if browser_result and browser_result.get("status") == "completed":
        include_research = st.checkbox("Include web research context", value=True, key="quick_report_include_research")

    if st.button("Generate Report", type="primary", key="quick_report_run"):
        if session_id is None:
            render_api_error(APIClientError("No active session and the backend is unreachable."))
            return
        result: dict[str, Any] | None
        with st.spinner("Building report..."):
            try:
                result = client.execute_report_agent(
                    session_id, dataset=pipeline_result["dataset"], cleaning_outcome=pipeline_result.get("cleaning"),
                    analysis_result=pipeline_result.get("analysis"), visualization_result=pipeline_result.get("visualization"),
                    browser_agent_result=browser_result if include_research else None,
                    report_config={"template_type": template_type, "theme": theme, "title": title or None},
                )
            except APIClientError as exc:
                render_api_error(exc)
                result = None
        if result is not None:
            state.current_report_agent_execution = result
            if result["status"] == "completed":
                state.current_report = result["report_document"]
                state.add_activity(f"Generated '{result['report_document']['title']}' from a quick run.")
                st.success(f"Report '{result['report_document']['title']}' generated — open it on the Reports page.")
            else:
                state.add_activity("Quick report generation failed.")


def _render_quick_actions(state: Any, client: APIClient, session_id: str | None) -> None:
    _render_quick_file_analysis(state, client, session_id)
    if state.current_agent_execution is not None:
        _render_quick_pipeline_result(state.current_agent_execution)
    st.divider()
    _render_quick_database_query(state, client, session_id)
    if state.current_agent_execution is not None:
        _render_quick_pipeline_result(state.current_agent_execution)
    st.divider()
    _render_quick_web_research(state, client, session_id)
    st.divider()
    _render_quick_report(state, client, session_id)


# -- Draft a Plan (preview/validate/edit/approve, sequential PlanExecutor) ----------------------


def _render_plan_decision_controls(state: Any, client: APIClient) -> None:
    st.markdown("**Review this plan**")
    plan = state.current_plan["execution_plan"]

    col1, col2, col3, col4 = st.columns(4)
    if col1.button("Preview"):
        try:
            preview = client.preview_plan(plan)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.markdown("Flowchart")
            st.code(preview["mermaid"], language="mermaid")
            st.markdown("Timeline")
            for entry in preview["timeline"]["entries"]:
                depends_on = ", ".join(entry["depends_on"]) or "none"
                st.markdown(f"{entry['order_index'] + 1}. {entry['name']} (depends on: {depends_on})")

    if col2.button("Validate"):
        try:
            validation = client.validate_plan(plan)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            result = validation["validation"]
            (st.success if result["is_valid"] else st.error)("Plan is valid." if result["is_valid"] else "Plan failed validation.")
            for issue in result["issues"]:
                (st.error if issue["severity"] == "error" else st.warning)(issue["message"])

    if col3.button("Approve & Run", type="primary"):
        try:
            executed = client.execute_plan(plan)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.current_plan_execution = executed
            if executed["status"] == "paused":
                st.warning("Plan paused — waiting for approval. See below.")
            else:
                st.success(f"Plan run — status: {executed['status']}")
            state.add_activity(f"Ran plan: {(plan.get('goal') or '')[:60]}")

    if col4.button("Discard plan"):
        state.current_plan = None
        st.rerun()

    with st.expander("Edit plan before running (advanced)"):
        edited_json = st.text_area("Plan JSON", value=json.dumps(plan, indent=2), height=300, key="plan_edit_json")
        if st.button("Apply edits"):
            try:
                edited_plan = json.loads(edited_json)
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
            else:
                state.current_plan = {**state.current_plan, "execution_plan": edited_plan}
                st.success("Edits applied — Preview or Validate again before approving.")
                st.rerun()


def _render_plan_execution_status(state: Any, client: APIClient) -> None:
    execution = state.current_plan_execution
    plan_id = execution["plan_id"]

    st.markdown("**Run status**")
    status = execution["status"]
    status_renderer = {"completed": st.success, "failed": st.error, "cancelled": st.error, "paused": st.warning}
    status_renderer.get(status, st.info)(f"Plan `{plan_id}` — status: **{status}**")

    if status == "paused":
        try:
            pending = [a for a in client.list_approvals_for_plan(plan_id) if a["status"] == "pending"]
        except APIClientError as exc:
            render_api_error(exc)
            pending = []

        if pending:
            approver = st.text_input("Your name (optional)", key="plan_approver_name")
        for approval in pending:
            node_name = approval["metadata"].get("node_name", "unknown step")
            with st.container(border=True):
                st.markdown(f"Waiting for approval before **{node_name}** runs.")
                if approval.get("reason"):
                    st.caption(approval["reason"])
                col1, col2 = st.columns(2)
                if col1.button("Approve", key=f"approve_{approval['approval_id']}", type="primary"):
                    try:
                        client.approve_approval(approval["approval_id"], approver=approver or None)
                    except APIClientError as exc:
                        render_api_error(exc)
                    else:
                        state.add_activity(f"Approved '{node_name}' for plan {plan_id}.")
                        st.rerun()
                if col2.button("Reject", key=f"reject_{approval['approval_id']}"):
                    try:
                        client.reject_approval(approval["approval_id"], approver=approver or None)
                        rejected_plan = client.reject_plan_execution(plan_id)
                    except APIClientError as exc:
                        render_api_error(exc)
                    else:
                        state.current_plan_execution = rejected_plan
                        state.add_activity(f"Rejected '{node_name}' for plan {plan_id}.")
                        st.rerun()

        col1, col2 = st.columns(2)
        if col1.button("Resume", type="primary"):
            try:
                resumed = client.resume_plan_execution(plan_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_plan_execution = resumed
                state.add_activity(f"Resumed plan {plan_id} — status: {resumed['status']}.")
                st.rerun()
        if col2.button("Cancel"):
            try:
                cancelled = client.cancel_plan_execution(plan_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_plan_execution = cancelled
                state.add_activity(f"Cancelled plan {plan_id}.")
                st.rerun()

    with st.expander("History"):
        try:
            history = client.get_plan_history(plan_id)
        except APIClientError as exc:
            render_api_error(exc)
            history = []
        if not history:
            st.caption("No history yet.")
        for event in history:
            detail = f" — {event['detail']}" if event.get("detail") else ""
            actor = f" (by {event['actor']})" if event.get("actor") else ""
            st.markdown(f"- **{event['event_type']}**{actor}{detail}")


def _render_draft_a_plan(state: Any, client: APIClient, session_id: str | None) -> None:
    st.caption(
        "Describe what you want in plain language; review, tweak, and approve the resulting plan "
        "before anything runs."
    )
    user_request = st.text_area(
        "What would you like InsightPilot to do?",
        placeholder="e.g. Clean my uploaded dataset and summarize key trends.", height=100, key="draft_plan_request",
    )

    if st.button("Draft Plan", type="primary", disabled=not user_request.strip(), key="draft_plan_generate"):
        if session_id is None:
            render_api_error(APIClientError("No active session and the backend is unreachable."))
        else:
            uploaded_datasets = [state.selected_dataset] if state.selected_dataset else []
            planner_result: dict[str, Any] | None
            with st.spinner("Drafting plan..."):
                try:
                    planner_result = client.create_plan(
                        user_request=user_request, session_id=session_id, uploaded_datasets=uploaded_datasets
                    )
                except APIClientError as exc:
                    render_api_error(exc)
                    planner_result = None

            if planner_result is not None:
                if planner_result["status"] == "completed" and planner_result["planner_output"] is not None:
                    state.current_plan = planner_result["planner_output"]
                    state.add_activity(f"Drafted a plan for: {user_request[:60]}")
                else:
                    for warning in planner_result.get("warnings", []):
                        st.error(warning)

    if state.current_plan is not None:
        st.divider()
        render_execution_plan(state.current_plan)
        _render_plan_decision_controls(state, client)

    if state.current_plan_execution is not None:
        st.divider()
        _render_plan_execution_status(state, client)


# -- Workflow Builder + My Workflows (existing Workflow Engine dashboard) -----------------------


def _render_builder(state: Any, client: APIClient) -> None:
    tab_objective, tab_steps = st.tabs(["From a goal", "From explicit steps"])

    with tab_objective:
        with st.form("build_from_objective"):
            objective = st.text_area("Goal", placeholder="e.g. Analyze the uploaded sales dataset and summarize key trends.")
            submitted = st.form_submit_button("Build Workflow", type="primary")
        if submitted and objective:
            try:
                workflow = client.create_workflow(objective=objective, session_id=state.session_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_workflow = workflow
                state.add_activity(f"Built workflow '{workflow['definition']['name']}' from a goal.")
                st.rerun()

    with tab_steps:
        st.caption("One step per line: `step_id,name,capability,dep1|dep2`. Leave dependencies blank for none.")
        with st.form("build_from_steps"):
            name = st.text_input("Workflow name")
            description = st.text_input("Description", value="")
            steps_text = st.text_area("Steps", placeholder="s1,Search the web,browser_agent,\ns2,Summarize,report_agent,s1")
            submitted = st.form_submit_button("Create Workflow", type="primary")
        if submitted and name and steps_text.strip():
            steps = []
            for line in steps_text.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                step_id, step_name, node_name = parts[0], parts[1], parts[2]
                deps = [d for d in parts[3].split("|") if d] if len(parts) > 3 and parts[3] else []
                steps.append({"step_id": step_id, "name": step_name, "node_name": node_name, "dependencies": deps})
            try:
                workflow = client.create_workflow(name=name, description=description, steps=steps)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_workflow = workflow
                state.add_activity(f"Created workflow '{workflow['definition']['name']}'.")
                st.rerun()

    with st.expander("Available capabilities"):
        st.caption("Names a step's own capability may reference right now.")
        try:
            system_status = client.get_system_status()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            agent_names = [node["name"] for node in system_status["graph_metadata"]["nodes"]]
            st.write(sorted(agent_names))


def _render_workflow_list(state: Any, client: APIClient) -> list[dict[str, Any]]:
    try:
        workflows = client.list_workflows()
    except APIClientError as exc:
        render_api_error(exc)
        return []
    if not workflows:
        st.info("No workflows yet — build one above.")
        return []
    st.dataframe(
        [
            {
                "ID": w["workflow_id"][:8], "Name": w["definition"]["name"], "Status": _status_label(w["status"]),
                "Steps": len(w["definition"]["steps"]), "Version": w["version"],
            }
            for w in workflows
        ],
        width="stretch", hide_index=True,
    )
    return workflows


def _render_workflow_details(state: Any, client: APIClient, workflows: list[dict[str, Any]]) -> None:
    if not workflows:
        return
    st.subheader("Workflow Details")
    options = {f"{w['definition']['name']} ({w['workflow_id'][:8]})": w["workflow_id"] for w in workflows}
    default = state.current_workflow["workflow_id"] if state.current_workflow else workflows[0]["workflow_id"]
    default_label = next((label for label, wid in options.items() if wid == default), next(iter(options)))
    chosen_label = st.selectbox("Select a workflow", list(options.keys()), index=list(options.keys()).index(default_label))
    workflow_id = options[chosen_label]

    try:
        workflow = client.get_workflow(workflow_id)
    except APIClientError as exc:
        render_api_error(exc)
        return
    state.current_workflow = workflow

    st.markdown(f"**{workflow['definition']['name']}** — {_status_label(workflow['status'])}")
    st.caption(workflow["definition"]["description"] or "_No description._")

    col1, col2, col3, col4 = st.columns(4)
    if col1.button("Run", type="primary"):
        try:
            execution = client.execute_workflow(workflow_id, state.session_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            # Bridge into the same execution-tracking state the Execution page reads,
            # so a workflow run's live per-step progress shows up there too —
            # WorkflowExecution.execution_id is the real underlying ExecutionService run.
            if execution.get("execution_id"):
                try:
                    state.current_dag_execution = client.get_execution(execution["execution_id"])
                except APIClientError:
                    pass
            state.add_activity(f"Ran workflow '{workflow['definition']['name']}' -> {execution['status']}.")
            st.rerun()
    if col2.button("Pause"):
        try:
            client.pause_workflow(workflow_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity("Paused workflow.")
            st.rerun()
    if col3.button("Resume"):
        try:
            client.resume_workflow(workflow_id, state.session_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity("Resumed workflow.")
            st.rerun()
    if col4.button("Cancel"):
        try:
            client.cancel_workflow(workflow_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity("Cancelled workflow.")
            st.rerun()

    st.caption("Track live progress and approvals for a running workflow on the **Execution** page.")

    with st.expander("Clone this workflow"):
        new_name = st.text_input("New name (optional)", key=f"clone_name_{workflow_id}")
        if st.button("Clone", key=f"clone_btn_{workflow_id}"):
            try:
                cloned = client.clone_workflow(workflow_id, new_name or None)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_workflow = cloned
                state.add_activity(f"Cloned workflow as '{cloned['definition']['name']}'.")
                st.rerun()

    st.markdown("**Steps**")
    st.dataframe(
        [
            {"Step": s["step_id"], "Name": s["name"], "Capability": s["node_name"], "Depends On": ", ".join(s["dependencies"]) or "—"}
            for s in workflow["definition"]["steps"]
        ],
        width="stretch", hide_index=True,
    )

    st.markdown("**Dependency Graph**")
    try:
        graph = client.get_workflow_graph(workflow_id)
    except APIClientError as exc:
        render_api_error(exc)
    else:
        st.code(graph, language="mermaid")

    st.markdown("**Statistics**")
    try:
        stats = client.get_workflow_statistics(workflow_id)
    except APIClientError as exc:
        render_api_error(exc)
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Runs", stats["total_executions"])
        col2.metric("Successful", stats["successful_executions"])
        col3.metric("Failed", stats["failed_executions"])
        col4.metric("Avg. duration (s)", f"{stats['average_duration_seconds']:.2f}")


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Planning", "Build a reusable workflow, run a quick one-off action, or draft and review a plan before running it.",
    icon="🧭",
)

session_id = ensure_session(state)
plain_client = APIClient(state.backend_url)

_render_approval_policy(plain_client)
st.divider()

tab_quick, tab_draft, tab_builder, tab_workflows = st.tabs(
    ["⚡ Quick Actions", "📝 Draft a Plan", "🧱 Workflow Builder", "📋 My Workflows"]
)
with tab_quick:
    _render_quick_actions(state, plain_client, session_id)
with tab_draft:
    _render_draft_a_plan(state, plain_client, session_id)
with tab_builder:
    if not state.is_authenticated:
        st.info("Log in on the **Settings** page first — building a workflow requires authentication.")
    else:
        _render_builder(state, _authenticated_client(state))
with tab_workflows:
    if not state.is_authenticated:
        st.info("Log in on the **Settings** page first — every workflow endpoint requires authentication.")
    else:
        auth_client = _authenticated_client(state)
        workflows = _render_workflow_list(state, auth_client)
        _render_workflow_details(state, auth_client, workflows)

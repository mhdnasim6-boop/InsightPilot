"""SQL page: connect to a relational database, browse tables, preview, and import.

Presentation only — every table list, preview row, and imported dataset
came from ``SQLDataSourceService`` over HTTP; this page never opens a
database connection itself. No natural-language input anywhere on this
page: the only way to run arbitrary SQL is the literal "custom query"
text box the backend's ``execute_query()``/``import_query()`` already
support.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state
from frontend.utils import format_bytes, format_number

_IMPLEMENTED_DATABASE_TYPES = ["sqlite", "postgresql", "mysql"]
_DATABASE_LABELS = {"sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL"}
_FILE_BASED_DATABASE_TYPES = {"sqlite"}
_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}


def _render_connection_form(state: Any) -> None:
    st.subheader("Connect")
    with st.form("sql_connection_form"):
        database_type = st.selectbox(
            "Database type", _IMPLEMENTED_DATABASE_TYPES, format_func=lambda value: _DATABASE_LABELS[value]
        )

        if database_type in _FILE_BASED_DATABASE_TYPES:
            database = st.text_input("Database file path", placeholder="/path/to/database.db")
            host = port = username = password = None
            ssl = False
        else:
            col1, col2 = st.columns(2)
            host = col1.text_input("Host")
            port = col2.number_input(
                "Port", min_value=1, max_value=65535, value=_DEFAULT_PORTS.get(database_type), step=1
            )
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            database = st.text_input("Database name")
            ssl = st.toggle("Use SSL", value=False)

        timeout = st.number_input("Timeout (seconds)", min_value=1.0, value=30.0, step=1.0)
        submitted = st.form_submit_button("Test Connection", type="primary")

    st.caption("More database types are coming soon.")

    if not submitted:
        return

    connection = {
        "database_type": database_type,
        "host": host or None,
        "port": int(port) if port else None,
        "database": database,
        "username": username or None,
        "password": password or None,
        "ssl": ssl,
        "timeout": timeout,
    }

    client = APIClient(state.backend_url)
    with st.spinner("Testing connection..."):
        try:
            result = client.connect_sql(connection)
        except APIClientError as exc:
            render_api_error(exc)
            return

    if result["is_valid"]:
        st.success(result["message"])
        state.sql_connection = connection
        state.add_activity(f"Connected to {_DATABASE_LABELS[database_type]} database '{database}'.")
    else:
        st.error(result["message"])
        for issue in result.get("issues", []):
            st.warning(f"[{issue['code']}] {issue['message']}")


def _render_table_metadata(metadata: dict[str, Any]) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", format_number(metadata["row_count"], decimals=0))
    col2.metric("Columns", format_number(len(metadata["columns"]), decimals=0))
    col3.metric("Estimated Size", format_bytes(metadata["estimated_size_bytes"]))

    st.dataframe(
        [
            {
                "Column": column["name"],
                "Type": column["data_type"],
                "Nullable": column["nullable"],
                "Primary Key": column["primary_key"],
            }
            for column in metadata["columns"]
        ],
        width="stretch",
        hide_index=True,
    )
    if metadata["foreign_keys"]:
        fk_descriptions = [f"{fk['constrained_columns']} -> {fk['referred_table']}" for fk in metadata["foreign_keys"]]
        st.caption("Foreign keys: " + ", ".join(fk_descriptions))
    if metadata["indexes"]:
        index_descriptions = [index["name"] or ", ".join(index["column_names"]) for index in metadata["indexes"]]
        st.caption("Indexes: " + ", ".join(index_descriptions))


def _render_table_browser(state: Any, connection: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Table Browser")
    client = APIClient(state.backend_url)

    try:
        tables = client.list_sql_tables(connection)
    except APIClientError as exc:
        render_api_error(exc)
        return

    if not tables:
        st.info("This database has no tables.")
        return

    table_name = st.selectbox("Table", tables)
    limit = st.slider("Preview rows", min_value=5, max_value=100, value=10)

    if st.button("Preview Table"):
        with st.spinner("Fetching preview..."):
            try:
                response = client.preview_sql_table(connection, table_name, limit=limit)
            except APIClientError as exc:
                render_api_error(exc)
                response = None
        if response is not None:
            st.dataframe(response["preview"]["rows"], width="stretch", hide_index=True)
            if response.get("metadata"):
                with st.expander("Table structure"):
                    _render_table_metadata(response["metadata"])

    dataset_name = st.text_input("Dataset name", value=table_name, key="sql_table_dataset_name")
    if st.button("Import Table", type="primary"):
        with st.spinner("Importing..."):
            try:
                dataset = client.import_sql_table(connection, table_name, dataset_name=dataset_name)
            except APIClientError as exc:
                render_api_error(exc)
                dataset = None
        if dataset is not None:
            state.selected_dataset = dataset
            state.current_analysis = None
            state.current_visualization = None
            state.add_activity(f"Imported table '{table_name}' as dataset '{dataset['dataset_name']}'.")
            st.success(f"Imported '{dataset['dataset_name']}' ({dataset['row_count']} rows).")


def _render_custom_query(state: Any, connection: dict[str, Any]) -> None:
    st.divider()
    st.subheader("Custom Query")
    client = APIClient(state.backend_url)

    query = st.text_area("SQL query", placeholder="SELECT * FROM my_table WHERE ...", height=100)
    limit = st.slider("Preview rows", min_value=5, max_value=100, value=10, key="query_preview_limit")

    if query and st.button("Preview Query"):
        with st.spinner("Running query..."):
            try:
                response = client.preview_sql_query(connection, query, limit=limit)
            except APIClientError as exc:
                render_api_error(exc)
                response = None
        if response is not None:
            st.dataframe(response["preview"]["rows"], width="stretch", hide_index=True)

    dataset_name = st.text_input("Dataset name", key="sql_query_dataset_name")
    if query and dataset_name and st.button("Import Query Result", type="primary"):
        with st.spinner("Importing..."):
            try:
                dataset = client.import_sql_query(connection, query, dataset_name=dataset_name)
            except APIClientError as exc:
                render_api_error(exc)
                dataset = None
        if dataset is not None:
            state.selected_dataset = dataset
            state.current_analysis = None
            state.current_visualization = None
            state.add_activity(f"Imported a custom query as dataset '{dataset['dataset_name']}'.")
            st.success(f"Imported '{dataset['dataset_name']}' ({dataset['row_count']} rows).")


state = get_dashboard_state()
render_sidebar(state)
page_header("Import from SQL", "Connect to a database, browse tables, preview, and import.", icon="🗄️")

_render_connection_form(state)

connection = state.sql_connection
if connection is not None:
    database_label = _DATABASE_LABELS.get(connection["database_type"], connection["database_type"])
    st.caption(f"Connected: {database_label} — {connection['database']}")
    _render_table_browser(state, connection)
    _render_custom_query(state, connection)

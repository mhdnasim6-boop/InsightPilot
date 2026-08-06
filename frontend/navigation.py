"""The single place the entire sidebar navigation tree is defined.

Kept separate from ``app.py`` deliberately: ``build_navigation()`` is a
plain function returning a ``dict[str, list[st.Page]]`` with no
Streamlit *runtime* dependency beyond constructing ``st.Page`` objects
(which is safe to do outside a live script run) — so "does the Advanced
section disappear when advanced_mode is off" is a plain Python
assertion (see ``tests/test_frontend_navigation.py``), not something
that requires driving a real browser or a full app run to verify.

Every ``st.Page`` here references an *existing* page file by its current
path — no file was renamed to build this nav tree. Section order below
is the literal order requested: Dashboard, Data, Prepare, Analyze,
Visualize, AI Copilot, Reports, Workflows, Settings, and (only when
``advanced_mode`` is on) Advanced.
"""

import streamlit as st
from streamlit.navigation.page import StreamlitPage


def build_navigation(advanced_mode: bool) -> dict[str, list[StreamlitPage]]:
    """Return the grouped nav dict for ``st.navigation()``.

    ``advanced_mode`` is a pure product/IA preference (see
    ``DashboardState.advanced_mode``) — it only decides what the sidebar
    *offers*. Every advanced page still enforces its own real permissions
    server-side regardless of this flag, and is still reachable by
    direct URL even when hidden here.
    """
    nav: dict[str, list[StreamlitPage]] = {
        "🏠 Dashboard": [st.Page("pages/0_Dashboard.py", title="Dashboard", icon="🏠", default=True)],
        "📂 Data": [
            st.Page("pages/1_Upload.py", title="Upload Data", icon="⬆️"),
            st.Page("pages/2_Datasets.py", title="My Datasets", icon="📂"),
            st.Page("pages/10_SQL.py", title="Import from SQL", icon="🗄️"),
        ],
        "🧹 Prepare": [st.Page("pages/3_Cleaning.py", title="Clean Data", icon="🧹")],
        "📊 Analyze": [st.Page("pages/4_Analysis.py", title="Analysis", icon="📊")],
        "📈 Visualize": [st.Page("pages/5_Visualization.py", title="Dashboards & Charts", icon="📈")],
        "🤖 AI Copilot": [st.Page("pages/9_Chat.py", title="Chat", icon="🤖")],
        "📑 Reports": [
            st.Page("pages/11_Reports.py", title="Reports", icon="📑"),
            st.Page("pages/28_ExecutiveSummary.py", title="Executive Summary", icon="📝"),
        ],
        "⚙️ Workflows": [
            st.Page("pages/23_Workflows.py", title="Planning", icon="🧭"),
            st.Page("pages/15_Execution.py", title="Execution", icon="▶️"),
        ],
        "🔧 Settings": [st.Page("pages/7_Settings.py", title="Settings", icon="🔧")],
    }

    if advanced_mode:
        nav["🛠️ Advanced"] = [
            st.Page("pages/12_MCP.py", title="MCP", icon="🔌"),
            st.Page("pages/13_Observability.py", title="Observability", icon="🔍"),
            st.Page("pages/16_Memory.py", title="Memory", icon="🧠"),
            st.Page("pages/17_Collaboration.py", title="Collaboration", icon="🤝"),
            st.Page("pages/18_Reflection.py", title="Reflection", icon="🪞"),
            st.Page("pages/19_Adaptive.py", title="Adaptive", icon="🧮"),
            st.Page("pages/20_Plugins.py", title="Plugins", icon="🧩"),
            st.Page("pages/21_Operations.py", title="Operations", icon="🛠️"),
            st.Page("pages/22_Security.py", title="Security", icon="🔐"),
            st.Page("pages/24_Live.py", title="Live", icon="📡"),
            st.Page("pages/25_Distributed.py", title="Distributed", icon="🖧"),
            st.Page("pages/26_Federation.py", title="Federation", icon="🌐"),
            st.Page("pages/27_Autonomous.py", title="Autonomous", icon="⚙️"),
            st.Page("pages/8_System.py", title="System", icon="💻"),
        ]

    return nav

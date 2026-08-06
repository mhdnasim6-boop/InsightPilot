"""Tests for frontend.navigation.build_navigation — the single source of truth for
the sidebar nav tree. Structural assertions only (dict keys / list lengths): a bare
``st.Page`` constructed outside a live Streamlit run cannot have its ``.title``/
``.icon`` introspected (Streamlit resolves those lazily against the running script's
own context), so these tests check shape, not rendered labels — actual rendering is
covered by AppTest smoke checks against the real running app.
"""

from frontend.navigation import build_navigation

_CORE_SECTIONS = {
    "🏠 Dashboard", "📂 Data", "🧹 Prepare", "📊 Analyze", "📈 Visualize",
    "🤖 AI Copilot", "📑 Reports", "⚙️ Workflows", "🔧 Settings",
}


def test_core_sections_are_always_present() -> None:
    for advanced_mode in (False, True):
        assert _CORE_SECTIONS.issubset(build_navigation(advanced_mode).keys())


def test_advanced_section_absent_when_advanced_mode_is_off() -> None:
    nav = build_navigation(False)
    assert "🛠️ Advanced" not in nav


def test_advanced_section_present_when_advanced_mode_is_on() -> None:
    nav = build_navigation(True)
    assert "🛠️ Advanced" in nav
    assert len(nav["🛠️ Advanced"]) == 14


def test_no_other_sections_leak_in_when_advanced_mode_is_off() -> None:
    nav = build_navigation(False)
    assert set(nav.keys()) == _CORE_SECTIONS


def test_data_section_has_three_pages() -> None:
    assert len(build_navigation(False)["📂 Data"]) == 3


def test_reports_section_has_two_pages() -> None:
    assert len(build_navigation(False)["📑 Reports"]) == 2


def test_workflows_section_has_two_pages() -> None:
    assert len(build_navigation(False)["⚙️ Workflows"]) == 2


def test_dashboard_section_has_exactly_one_page() -> None:
    assert len(build_navigation(False)["🏠 Dashboard"]) == 1


def test_total_page_count_matches_every_surviving_page_file() -> None:
    nav = build_navigation(True)
    total = sum(len(pages) for pages in nav.values())
    assert total == 27

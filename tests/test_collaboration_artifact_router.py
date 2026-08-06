"""Tests for ArtifactRouter: routes a producer's known result fields into a
dependent subtask's inputs by the same key convention ReportAgent/
ExecutiveSummaryAgent's own input validators already expect.
"""

from backend.collaboration.coordinator.artifact_router import ArtifactRouter


def test_route_fills_conventional_keys_from_file_agent_result() -> None:
    router = ArtifactRouter()
    producer_result = {"dataset": {"dataset_id": "d1"}, "cleaning": {"rows": 3}, "analysis": {"kpis": []}}

    routed, filled = router.route("file_agent", producer_result, {})

    assert routed["dataset"] == {"dataset_id": "d1"}
    assert routed["cleaning_outcome"] == {"rows": 3}
    assert routed["analysis_result"] == {"kpis": []}
    assert set(filled) == {"dataset", "cleaning_outcome", "analysis_result"}


def test_route_never_overwrites_an_explicit_input() -> None:
    router = ArtifactRouter()
    producer_result = {"dataset": {"dataset_id": "d1"}}

    routed, filled = router.route("file_agent", producer_result, {"dataset": {"dataset_id": "explicit"}})

    assert routed["dataset"] == {"dataset_id": "explicit"}
    assert filled == []


def test_route_skips_none_fields() -> None:
    router = ArtifactRouter()
    producer_result = {"dataset": None, "cleaning": {"rows": 3}}

    routed, _filled = router.route("file_agent", producer_result, {})

    assert "dataset" not in routed
    assert routed["cleaning_outcome"] == {"rows": 3}


def test_route_browser_agent_passes_whole_result() -> None:
    router = ArtifactRouter()
    producer_result = {"sources": [], "summaries": [{"query": "market trends"}]}

    routed, filled = router.route("browser_agent", producer_result, {})

    assert routed["browser_agent_result"] == producer_result
    assert filled == ["browser_agent_result"]


def test_route_unknown_producer_routes_nothing() -> None:
    router = ArtifactRouter()
    routed, filled = router.route("planner", {"execution_plan": {}}, {"a": 1})
    assert routed == {"a": 1}
    assert filled == []


def test_route_all_merges_every_dependency_in_order() -> None:
    router = ArtifactRouter()
    producers = {
        "st-file": ("file_agent", {"dataset": {"dataset_id": "d1"}, "analysis": {"kpis": []}}),
        "st-browser": ("browser_agent", {"sources": [], "summaries": []}),
    }

    routed, filled_by_producer = router.route_all(producers, {}, ["st-file", "st-browser"])

    assert routed["dataset"] == {"dataset_id": "d1"}
    assert routed["browser_agent_result"] == {"sources": [], "summaries": []}
    assert set(filled_by_producer["st-file"]) == {"dataset", "analysis_result"}
    assert filled_by_producer["st-browser"] == ["browser_agent_result"]


def test_route_all_ignores_dependencies_with_no_result_yet() -> None:
    router = ArtifactRouter()
    routed, filled_by_producer = router.route_all({}, {"a": 1}, ["st-not-done-yet"])
    assert routed == {"a": 1}
    assert filled_by_producer == {}

"""Tests for GraphBuilder: registration, validation, compilation, export."""

import pytest
from langgraph.graph import END

from backend.orchestration.exceptions import GraphValidationError
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.placeholders import EndNode, PlannerNode, RouterNode


def test_validate_fails_without_entry_point() -> None:
    builder = GraphBuilder()
    builder.add_node(PlannerNode())

    with pytest.raises(GraphValidationError):
        builder.validate()


def test_validate_fails_on_dangling_edge() -> None:
    builder = GraphBuilder()
    planner = PlannerNode()
    builder.add_node(planner)
    builder.set_entry_point(planner.name)
    builder.add_edge(planner.name, "not-a-real-node")

    with pytest.raises(GraphValidationError):
        builder.validate()


def test_valid_graph_compiles_successfully() -> None:
    builder = GraphBuilder()
    planner, router, end = PlannerNode(), RouterNode(), EndNode()
    builder.add_node(planner)
    builder.add_node(router)
    builder.add_node(end)
    builder.set_entry_point(planner.name)
    builder.add_edge(planner.name, router.name)
    builder.add_edge(router.name, end.name)
    builder.add_edge(end.name, END)

    compiled = builder.compile()

    assert set(compiled.nodes) == {"planner", "router", "end"}
    assert compiled.entry_point == "planner"


def test_export_returns_graph_metadata_matching_registration() -> None:
    builder = GraphBuilder()
    planner, router = PlannerNode(), RouterNode()
    builder.add_node(planner)
    builder.add_node(router)
    builder.set_entry_point(planner.name)
    builder.add_edge(planner.name, router.name)

    metadata = builder.export()

    assert {node.name for node in metadata.nodes} == {"planner", "router"}
    assert (metadata.edges[0].source, metadata.edges[0].target) == ("planner", "router")
    assert metadata.entry_point == "planner"

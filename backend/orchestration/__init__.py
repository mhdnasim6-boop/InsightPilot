"""Reusable graph orchestration infrastructure, backed internally by LangGraph.

LangGraph is an implementation detail: only ``graph/builder.py``,
``graph/default_graph.py``, ``graph/compiled.py``, ``execution/engine.py``,
and ``visualization/mermaid.py`` import it. Everything else — and
everything outside this package — depends only on ``InsightPilotState``,
``GraphMetadata``, and the ``OrchestrationNode`` interface.
"""

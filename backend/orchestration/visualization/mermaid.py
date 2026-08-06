"""Graph visualization: Mermaid text (always available) and PNG (best-effort, local-only).

Mermaid text needs nothing beyond LangGraph itself and never touches the
network — it's the primary artifact meant for documentation (GitHub,
most IDEs, and any standard Mermaid renderer turn a mermaid code fence
into a diagram automatically). PNG rendering is attempted locally via
graphviz; if that optional system dependency isn't installed, this
degrades to returning ``None`` rather than failing.

Deliberately not offered here: LangGraph's own network-based Mermaid PNG
API (``draw_mermaid_png``). Defaulting to a live third-party call would
make this "infrastructure" secretly depend on the network and a remote
service being up — the opposite of what a Mock/local-first project wants.
Direct SVG export isn't produced for the same reason: the underlying
library doesn't offer a local, network-free SVG renderer today. The
Mermaid text output remains SVG-renderable by any standard Mermaid tool.
"""

from loguru import logger

from backend.orchestration.graph.compiled import CompiledGraph


def generate_mermaid(graph: CompiledGraph) -> str:
    """Render the compiled graph as Mermaid flowchart text."""
    return graph.compiled.get_graph().draw_mermaid()


def generate_png(graph: CompiledGraph) -> bytes | None:
    """Render the compiled graph as a PNG, using local graphviz rendering only.

    Returns None (and logs a warning) if graphviz/pygraphviz isn't
    installed, rather than raising or falling back to a network call.
    """
    try:
        # output_file_path=None selects the "return bytes" overload rather than
        # "write to disk and return None" — passing it explicitly (its runtime
        # default) is required for mypy to resolve draw_png's overload set.
        return graph.compiled.get_graph().draw_png(output_file_path=None)
    except Exception as exc:  # noqa: BLE001 - any rendering-backend failure should degrade to None, not crash
        logger.warning("PNG graph rendering unavailable: {}", exc)
        return None

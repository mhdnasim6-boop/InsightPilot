"""Configuration for compiling and running an orchestration graph.

These map directly onto LangGraph's own compile-time and per-node
options. This file (and ``builder.py``, ``compiled.py``,
``default_graph.py``) are the only places allowed to know that
vocabulary exists.
"""

from pydantic import BaseModel, Field


class GraphConfig(BaseModel):
    """Tunables for a compiled graph: iteration limits, timeouts, retries, interrupts, debug."""

    max_iterations: int = Field(default=25, gt=0, description="LangGraph recursion_limit at run time.")
    timeout_seconds: float | None = Field(default=None, gt=0.0, description="Per-node execution timeout.")
    retry_max_attempts: int = Field(default=1, ge=1, description="Per-node retry attempts on failure.")
    interrupt_before: list[str] = Field(default_factory=list)
    interrupt_after: list[str] = Field(default_factory=list)
    debug: bool = False

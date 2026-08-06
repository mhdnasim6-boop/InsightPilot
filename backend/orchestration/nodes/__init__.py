"""The common node interface, placeholder nodes, and the first real one.

``FileAgentNode`` (in ``file_agent_node.py``) is the first business
agent wired into the default graph — a thin adapter over
``backend.agents.file``. ``PlannerNode``/``EndNode`` (``placeholders.py``)
remain placeholders; ``RouterNode`` is still defined there too, for a
future conditional-routing need, just no longer wired into the default
graph. Future business agents (SQL, Analysis, ...) implement
``OrchestrationNode`` exactly like these do — ``GraphBuilder`` and
``ExecutionEngine`` never know or care which concrete node type they're
driving.
"""

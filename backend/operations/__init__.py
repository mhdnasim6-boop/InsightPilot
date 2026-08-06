"""Operations layer: configuration profiles, environment validation,
health/readiness/diagnostics, feature flags, and startup/shutdown
coordination — the production-readiness layer around InsightPilot.

Infrastructure only: nothing here touches Agent/Tool/Planner/Memory/
Reflection/Adaptive Planning/Collaboration/Execution Engine/Plugin logic.
Every operational concern is composed from already-existing services
(``HealthService``, ``PluginRegistry``, ``ToolRegistry``, ``MemoryService``,
...), never a reimplementation of them.
"""

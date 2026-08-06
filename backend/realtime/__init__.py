"""Realtime Event Streaming & Live Collaboration layer.

Pure event-transport addition on top of every existing subsystem
(Planner, ExecutionService, WorkflowService, Agents, Tools, Memory,
Observability, Reflection, Adaptive Planning, Plugins, Security) — none
of them are modified; this package only observes their already-public
calls/results (via thin, transparent decorators in ``publishers/``,
exactly mirroring the existing ``TracingTool`` precedent) and forwards
typed events through ``RealtimeService``, the one and only public API
this package exposes.
"""

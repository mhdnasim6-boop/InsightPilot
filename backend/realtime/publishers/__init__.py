"""Publishers: transparent decorators translating each protected subsystem's
own calls/results into typed realtime Events, published through
RealtimeService. Every class here mirrors the existing
``backend.observability.services.tracing_tool.TracingTool`` precedent —
wrap, delegate, never reimplement — so none of the wrapped subsystems'
own source is ever modified.
"""

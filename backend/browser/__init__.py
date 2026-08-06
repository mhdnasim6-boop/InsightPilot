"""External-context retrieval: BrowserService and the provider abstraction beneath it.

Mirrors ``backend.ai`` in shape: ``BrowserService`` (in
``backend.services.browser_service``) is the one object anything should
use, ``BrowserProvider`` is the seam a real (or MCP-backed) backend
plugs into later, and ``MockBrowserProvider`` is today's deterministic,
network-free default. Nothing here performs business analysis — this
package only ever produces ``SourceResult``/``SearchOutcome``, never an
``AnalysisResult``.
"""

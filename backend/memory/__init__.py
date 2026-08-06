"""Long-term memory & knowledge layer: a generic, architecture-wide store every
agent/service can write structured knowledge into and query back out of.

Not chat history — a knowledge layer. Deterministic throughout: no vector
database, no embeddings, no FAISS/ChromaDB, no LangChain, no RAG. Every
retrieval/ranking/summarization operation here is a plain, inspectable
function over structured fields (keywords, tags, type, scope, dates,
importance) — never a similarity score over an opaque vector. This
keeps the door open for a future vector-backed implementation to plug in
*underneath* ``MemoryService``'s public API without changing it, exactly
like ``backend.tools.base.tool.Tool`` was designed so a future
MCP-backed tool could be a drop-in registry entry.
"""

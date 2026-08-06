"""Memory endpoints: create, list, fetch, delete, search, summarize,
statistics, and export (JSON/Markdown).

Thin HTTP wrappers only — every endpoint here is a direct call into
``MemoryService``, never a parallel implementation. Route order
matters: ``/memory/statistics`` and ``/memory/export/(json|markdown)``
are registered before ``/memory/{memory_id}`` so FastAPI matches them
as literal path segments rather than treating "statistics"/"export" as
a memory_id (same reasoning as ``/approvals/policy`` vs.
``/approvals/{approval_id}``).
"""

from typing import Literal

from fastapi import APIRouter, Depends

from backend.dependencies.memory import get_memory_service
from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_result import MemoryResult
from backend.memory.models.memory_statistics import MemoryStatistics
from backend.memory.services.memory_service import MemoryService
from backend.schemas.memory_request import MemoryCreateRequest, MemorySummarizeRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/memory")


@router.post("", response_model=SuccessResponse[MemoryItem], summary="Remember a new memory")
async def remember_memory(
    request: MemoryCreateRequest, memory_service: MemoryService = Depends(get_memory_service)
) -> SuccessResponse[MemoryItem]:
    """Store a new memory."""
    item = memory_service.remember(
        title=request.title,
        summary=request.summary,
        memory_type=request.memory_type,
        scope=request.scope,
        content=request.content,
        tags=request.tags,
        importance=request.importance,
        references=request.references,
        metadata=request.metadata,
    )
    return SuccessResponse.ok(data=item, message=f"Memory '{item.memory_id}' remembered.")


@router.get("", response_model=SuccessResponse[list[MemoryItem]], summary="List every memory")
async def list_memories(
    memory_service: MemoryService = Depends(get_memory_service),
) -> SuccessResponse[list[MemoryItem]]:
    """Return every stored memory, most recently added first."""
    return SuccessResponse.ok(data=memory_service.list_all(), message="Memories fetched.")


@router.post("/search", response_model=SuccessResponse[MemoryResult], summary="Search memories")
async def search_memories(
    query: MemoryQuery, memory_service: MemoryService = Depends(get_memory_service)
) -> SuccessResponse[MemoryResult]:
    """Deterministically filter, rank, and top-k the stored memories against ``query``."""
    return SuccessResponse.ok(data=memory_service.search(query), message="Search complete.")


@router.post("/summarize", response_model=SuccessResponse[str], summary="Summarize memories")
async def summarize_memories(
    request: MemorySummarizeRequest, memory_service: MemoryService = Depends(get_memory_service)
) -> SuccessResponse[str]:
    """Deterministically, extractively summarize the memories matching ``query`` (or all of them)."""
    summary = memory_service.summarize(request.query, max_length=request.max_length)
    return SuccessResponse.ok(data=summary, message="Summary generated.")


@router.get("/statistics", response_model=SuccessResponse[MemoryStatistics], summary="Get memory statistics")
async def get_memory_statistics(
    memory_service: MemoryService = Depends(get_memory_service),
) -> SuccessResponse[MemoryStatistics]:
    """Aggregate counts, recency, and average importance over every stored memory."""
    return SuccessResponse.ok(data=memory_service.statistics(), message="Statistics fetched.")


@router.get("/export/{export_format}", response_model=SuccessResponse[str], summary="Export memories")
async def export_memories(
    export_format: Literal["json", "markdown"], memory_service: MemoryService = Depends(get_memory_service)
) -> SuccessResponse[str]:
    """Export every stored memory as JSON or Markdown."""
    return SuccessResponse.ok(data=memory_service.export(export_format), message=f"Memories exported as {export_format}.")


@router.delete("", response_model=SuccessResponse[bool], summary="Clear every memory")
async def clear_memories(memory_service: MemoryService = Depends(get_memory_service)) -> SuccessResponse[bool]:
    """Remove every stored memory. Used by the frontend's "Clear all" control."""
    memory_service.clear()
    return SuccessResponse.ok(data=True, message="All memories cleared.")


@router.get("/{memory_id}", response_model=SuccessResponse[MemoryItem], summary="Get one memory")
async def get_memory(
    memory_id: str, memory_service: MemoryService = Depends(get_memory_service)
) -> SuccessResponse[MemoryItem]:
    """Fetch one memory by id. Raises MemoryItemNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=memory_service.recall(memory_id), message="Memory fetched.")


@router.delete("/{memory_id}", response_model=SuccessResponse[bool], summary="Forget a memory")
async def forget_memory(
    memory_id: str, memory_service: MemoryService = Depends(get_memory_service)
) -> SuccessResponse[bool]:
    """Delete one memory by id."""
    deleted = memory_service.forget(memory_id)
    return SuccessResponse.ok(data=deleted, message=f"Memory '{memory_id}' forgotten." if deleted else "No such memory.")

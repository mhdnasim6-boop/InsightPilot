"""ExecutionCheckpointStore provider — its own module so both
``backend.dependencies.execution`` and ``backend.dependencies.distributed``
can depend on the exact same cached singleton without a circular import:
``distributed.py`` needs it for ``TaskRecovery`` (to check whether a step
already really completed before requeuing it); ``execution.py`` needs
``distributed.py`` for ``DispatchingAgentService`` (Phase 38's dispatch
wrap in ``get_node_dispatcher()``). Both edges together would cycle if
this provider lived in either of those two modules, so it lives here
instead — ``execution.py`` re-exports it via a plain import (not a
redefinition) so every existing caller of
``backend.dependencies.execution.get_execution_checkpoint_store`` is
completely unaffected.
"""

from functools import lru_cache

from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore


@lru_cache
def get_execution_checkpoint_store() -> ExecutionCheckpointStore:
    """Return the process-wide ExecutionCheckpointStore singleton."""
    return ExecutionCheckpointStore()

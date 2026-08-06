"""LoadBalancer: a pure strategy over a set of already-eligible workers.

Deliberately knows nothing about capabilities, status, or leases —
``WorkerSelector`` filters down to the eligible candidate set first; this
class only answers "given these candidates, which one should get the
next task." Least-loaded by ``load_ratio()`` (active_tasks / capacity),
tie-broken by ``worker_id`` for deterministic, testable behavior.
"""

from backend.distributed.models.worker import Worker


class LoadBalancer:
    """Picks the least-loaded worker among a set of candidates."""

    def select(self, candidates: list[Worker]) -> Worker | None:
        """Return the least-loaded candidate, or None if ``candidates`` is empty."""
        if not candidates:
            return None
        return min(candidates, key=lambda worker: (worker.load_ratio(), worker.worker_id))

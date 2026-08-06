"""LeaseManager: issues, renews, and expires Leases.

A lease is the one piece of state that makes recovery honest: without
it, a worker that goes silent mid-task would appear to own that task
forever. ``ttl_seconds`` is this manager's own constructor argument
(configurable, like ``ReplayBuffer.capacity`` in the realtime layer),
not a global setting — the same "no new global Settings field for a
purely internal default" precedent.
"""

from datetime import datetime, timedelta

from backend.distributed.exceptions import LeaseNotFoundError
from backend.distributed.models.lease import Lease
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

DEFAULT_LEASE_TTL_SECONDS = 60.0


class LeaseManager:
    """Tracks every outstanding lease and its expiry."""

    def __init__(self, ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._leases: dict[str, Lease] = {}

    def grant(self, assignment_id: str, worker_id: str, now: datetime | None = None) -> Lease:
        """Issue a fresh lease for one assignment, owned by one worker."""
        granted_at = now or utc_now()
        lease = Lease(
            lease_id=generate_id(),
            assignment_id=assignment_id,
            worker_id=worker_id,
            granted_at=granted_at,
            expires_at=granted_at + timedelta(seconds=self._ttl_seconds),
        )
        self._leases[lease.lease_id] = lease
        return lease

    def get(self, lease_id: str) -> Lease:
        """Fetch a lease. Raises LeaseNotFoundError if unknown."""
        lease = self._leases.get(lease_id)
        if lease is None:
            raise LeaseNotFoundError(f"No lease found for '{lease_id}'.")
        return lease

    def renew(self, lease_id: str, now: datetime | None = None) -> Lease:
        """Extend a lease's expiry by another full TTL window from ``now``."""
        lease = self.get(lease_id)
        renewed_at = now or utc_now()
        renewed = lease.model_copy(
            update={
                "expires_at": renewed_at + timedelta(seconds=self._ttl_seconds),
                "renewed_count": lease.renewed_count + 1,
            }
        )
        self._leases[lease_id] = renewed
        return renewed

    def renew_all_for_worker(self, worker_id: str, now: datetime | None = None) -> list[Lease]:
        """Renew every lease currently owned by ``worker_id`` — what a heartbeat does."""
        return [self.renew(lease.lease_id, now) for lease in self.list_for_worker(worker_id)]

    def release(self, lease_id: str) -> None:
        """Release a lease outright (task completed/failed terminally). A no-op if unknown."""
        self._leases.pop(lease_id, None)

    def list_for_worker(self, worker_id: str) -> list[Lease]:
        """Every currently outstanding lease owned by ``worker_id``."""
        return [lease for lease in self._leases.values() if lease.worker_id == worker_id]

    def list_expired(self, now: datetime | None = None) -> list[Lease]:
        """Every currently outstanding lease whose expiry has already passed."""
        as_of = now or utc_now()
        return [lease for lease in self._leases.values() if lease.is_expired(as_of)]

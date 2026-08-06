"""Tests for the abstract CheckpointInterface contract."""

import asyncio

import pytest

from backend.orchestration.checkpoints.base import CheckpointInterface
from backend.orchestration.state.state import InsightPilotState
from backend.utils.time import utc_now


def test_checkpoint_interface_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        CheckpointInterface()  # type: ignore[abstract]


def test_a_well_formed_implementation_satisfies_the_contract() -> None:
    """No implementation ships in this phase — this just proves the contract is usable."""

    class InMemoryStub(CheckpointInterface):
        def __init__(self) -> None:
            self._snapshots: dict[str, list[InsightPilotState]] = {}

        async def save(self, execution_id: str, state: InsightPilotState) -> None:
            self._snapshots.setdefault(execution_id, []).append(state)

        async def load(self, execution_id: str) -> InsightPilotState | None:
            snapshots = self._snapshots.get(execution_id)
            return snapshots[-1] if snapshots else None

        async def list_checkpoints(self, execution_id: str) -> list[InsightPilotState]:
            return list(self._snapshots.get(execution_id, []))

        async def delete(self, execution_id: str) -> bool:
            return self._snapshots.pop(execution_id, None) is not None

    async def scenario() -> None:
        stub = InMemoryStub()
        now = utc_now()
        state = InsightPilotState(execution_id="e1", created_at=now, updated_at=now)

        assert await stub.load("e1") is None

        await stub.save("e1", state)
        loaded = await stub.load("e1")
        assert loaded is not None
        assert loaded.execution_id == "e1"

        assert await stub.list_checkpoints("e1") == [state]
        assert await stub.delete("e1") is True
        assert await stub.delete("e1") is False

    asyncio.run(scenario())

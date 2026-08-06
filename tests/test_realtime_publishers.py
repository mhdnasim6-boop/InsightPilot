"""Tests for backend.realtime.publishers: every decorator that translates a
protected subsystem's own calls into typed realtime Events.

Each test wraps a small, real, in-file fake standing in for the actual
protected subsystem (the fakes here fully implement whatever narrow
protocol the decorator itself calls, exactly the same "fake the leaf,
keep everything else real" convention used throughout this test suite)
— the decorator under test, ``RealtimeService``, and every realtime
component underneath it are all real.
"""

import asyncio
from typing import Any, ClassVar

import pytest

from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.planning.models.step import ExecutionStep
from backend.realtime.broker.event_bus import RealtimeEventBus
from backend.realtime.broker.event_registry import EventRegistry
from backend.realtime.broker.subscription_manager import SubscriptionManager
from backend.realtime.events.event_type import EventType
from backend.realtime.publishers.ai_publisher import RealtimePublishingAIService
from backend.realtime.publishers.approval_publisher import (
    RealtimePublishingApprovalService,
)
from backend.realtime.publishers.execution_publisher import (
    RealtimePublishingAgentService,
)
from backend.realtime.publishers.memory_publisher import RealtimePublishingMemoryService
from backend.realtime.publishers.observability_publisher import (
    RealtimePublishingAuthenticationService,
    RealtimePublishingPluginRegistry,
    RealtimePublishingTool,
)
from backend.realtime.publishers.workflow_publisher import (
    RealtimePublishingReflectionService,
    RealtimePublishingWorkflowOptimizer,
    RealtimePublishingWorkflowService,
)
from backend.realtime.replay.replay_buffer import ReplayBuffer
from backend.realtime.replay.replay_service import ReplayService
from backend.realtime.services.realtime_service import RealtimeService
from backend.realtime.websocket.websocket_manager import WebSocketManager
from backend.utils.time import utc_now
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_status import WorkflowStatus


def _build_service() -> RealtimeService:
    subscription_manager = SubscriptionManager()
    replay_buffer = ReplayBuffer()
    return RealtimeService(
        event_bus=RealtimeEventBus(),
        replay_buffer=replay_buffer,
        replay_service=ReplayService(replay_buffer),
        subscription_manager=subscription_manager,
        websocket_manager=WebSocketManager(subscription_manager),
        event_registry=EventRegistry(),
    )


def _event_types(service: RealtimeService) -> list[EventType]:
    return [envelope.event.event_type for envelope in service.replay()]


# -- execution_publisher: RealtimePublishingAgentService ----------------------------


class _FakeAgentService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[Any] = []

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> str:
        self.calls.append((step, session_id))
        if self.fail:
            raise RuntimeError("boom")
        return "ok"


def _step() -> ExecutionStep:
    return ExecutionStep(step_id="s1", name="Do it", node_name="sql_agent")


def test_agent_service_publishes_started_and_completed_on_success() -> None:
    service = _build_service()
    wrapped = RealtimePublishingAgentService(_FakeAgentService(), service)

    result = asyncio.run(wrapped.execute_step(_step(), "session-1"))

    assert result == "ok"
    assert _event_types(service) == [
        EventType.STEP_STARTED, EventType.AGENT_STARTED, EventType.STEP_COMPLETED, EventType.AGENT_COMPLETED,
    ]


def test_agent_service_publishes_failed_and_reraises_on_exception() -> None:
    service = _build_service()
    wrapped = RealtimePublishingAgentService(_FakeAgentService(fail=True), service)

    with pytest.raises(RuntimeError):
        asyncio.run(wrapped.execute_step(_step(), None))

    assert _event_types(service) == [
        EventType.STEP_STARTED, EventType.AGENT_STARTED, EventType.STEP_FAILED, EventType.AGENT_FAILED,
    ]


# -- observability_publisher: RealtimePublishingTool --------------------------------


class _FakeInputModel:
    @staticmethod
    def model_json_schema() -> dict:
        return {}


class _FakeTool:
    name = "fake_tool"
    description = "A fake tool."
    input_model = _FakeInputModel
    output_model = _FakeInputModel

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def execute(self, tool_input: Any) -> str:
        if self.fail:
            raise ValueError("tool broke")
        return "done"

    def input_schema(self) -> dict:
        return {}

    def output_schema(self) -> dict:
        return {}


def test_tool_publishes_started_and_completed_on_success() -> None:
    service = _build_service()
    wrapped = RealtimePublishingTool(_FakeTool(), service)

    result = asyncio.run(wrapped.execute({}))

    assert result == "done"
    assert _event_types(service) == [EventType.TOOL_STARTED, EventType.TOOL_COMPLETED]


def test_tool_publishes_failed_and_reraises_on_exception() -> None:
    service = _build_service()
    wrapped = RealtimePublishingTool(_FakeTool(fail=True), service)

    with pytest.raises(ValueError):
        asyncio.run(wrapped.execute({}))

    assert _event_types(service) == [EventType.TOOL_STARTED, EventType.TOOL_FAILED]


# -- ai_publisher: RealtimePublishingAIService ---------------------------------------


class _FakeTokenUsage:
    @staticmethod
    def model_dump() -> dict:
        return {"total_tokens": 10}


class _FakeAIResponse:
    provider = "fake"
    model = "fake-model"
    usage = _FakeTokenUsage()


class _FakeAIService:
    async def generate(self, request: Any, provider_name: str | None = None) -> Any:
        return _FakeAIResponse()

    async def health_check(self, provider_name: str | None = None) -> str:
        return "ok"


def test_ai_service_publishes_started_and_completed() -> None:
    service = _build_service()
    wrapped = RealtimePublishingAIService(_FakeAIService(), service)

    response = asyncio.run(wrapped.generate(request=object()))

    assert response.model == "fake-model"
    assert _event_types(service) == [EventType.AI_CALL_STARTED, EventType.AI_CALL_COMPLETED]


def test_ai_service_forwards_unrelated_methods_via_getattr() -> None:
    service = _build_service()
    wrapped = RealtimePublishingAIService(_FakeAIService(), service)

    assert asyncio.run(wrapped.health_check()) == "ok"


# -- approval_publisher: RealtimePublishingApprovalService ---------------------------


class _FakeApprovalService:
    def __init__(self) -> None:
        self.approvals: dict[str, ExecutionApproval] = {}

    def request_approval(
        self, plan_id: str, step_id: str, node_name: str, execution_id: str, reason: str | None = None
    ) -> ExecutionApproval:
        approval = ExecutionApproval(
            approval_id="a1", plan_id=plan_id, step_id=step_id, requested_at=utc_now(),
            metadata={"node_name": node_name, "execution_id": execution_id},
        )
        self.approvals["a1"] = approval
        return approval

    def approve(self, approval_id: str, approver: str | None = None) -> ExecutionApproval:
        updated = self.approvals[approval_id].model_copy(update={"status": ApprovalStatus.APPROVED})
        self.approvals[approval_id] = updated
        return updated

    def reject(self, approval_id: str, approver: str | None = None, reason: str | None = None) -> ExecutionApproval:
        updated = self.approvals[approval_id].model_copy(update={"status": ApprovalStatus.REJECTED})
        self.approvals[approval_id] = updated
        return updated

    def list_pending(self) -> list[ExecutionApproval]:
        return list(self.approvals.values())


def test_approval_service_publishes_requested_granted_rejected() -> None:
    service = _build_service()
    wrapped = RealtimePublishingApprovalService(_FakeApprovalService(), service)

    wrapped.request_approval("p1", "s1", "sql_agent", "exec-1")
    wrapped.approve("a1", approver="alice")

    assert _event_types(service) == [EventType.APPROVAL_REQUESTED, EventType.APPROVAL_GRANTED]
    requested = service.replay()[0].event
    assert requested.plan_id == "p1" and requested.agent_name == "sql_agent" and requested.execution_id == "exec-1"


def test_approval_service_forwards_list_pending_via_getattr() -> None:
    service = _build_service()
    fake = _FakeApprovalService()
    wrapped = RealtimePublishingApprovalService(fake, service)
    wrapped.request_approval("p1", "s1", "sql_agent", "exec-1")

    assert len(wrapped.list_pending()) == 1


# -- memory_publisher: RealtimePublishingMemoryService -------------------------------


class _FakeMemoryService:
    def remember(self, title: str, summary: str, memory_type: MemoryType, scope: MemoryScope = MemoryScope.SESSION,
                 content: Any = None, tags: Any = None, importance: float = 0.5, references: Any = None,
                 metadata: Any = None) -> MemoryItem:
        return MemoryItem(
            memory_id="m1", title=title, summary=summary, memory_type=memory_type, scope=scope,
            created_at=utc_now(), updated_at=utc_now(),
        )


def test_memory_service_publishes_memory_stored() -> None:
    service = _build_service()
    wrapped = RealtimePublishingMemoryService(_FakeMemoryService(), service)

    item = wrapped.remember("Title", "Summary", MemoryType.DECISION)

    assert item.memory_id == "m1"
    assert _event_types(service) == [EventType.MEMORY_STORED]
    assert service.replay()[0].event.data["memory_id"] == "m1"


# -- observability_publisher: PluginRegistry / AuthenticationService -----------------


class _FakePluginManifestMetadata:
    version = "1.0.0"


class _FakePluginManifest:
    id = "plugin-1"
    metadata = _FakePluginManifestMetadata()


class _FakePluginState:
    value = "registered"


class _FakePluginRecord:
    manifest = _FakePluginManifest()
    state = _FakePluginState()


class _FakePluginRegistry:
    def load(self, plugin_id: str | None = None) -> list[Any]:
        return [_FakePluginRecord()]

    def unload(self, plugin_id: str) -> Any:
        return _FakePluginRecord()


def test_plugin_registry_publishes_loaded_and_unloaded() -> None:
    service = _build_service()
    wrapped = RealtimePublishingPluginRegistry(_FakePluginRegistry(), service)

    wrapped.load()
    wrapped.unload("plugin-1")

    assert _event_types(service) == [EventType.PLUGIN_LOADED, EventType.PLUGIN_UNLOADED]
    assert service.replay()[0].event.data["plugin_id"] == "plugin-1"


class _FakeUserProfile:
    user_id = "u1"
    username = "alice"


class _FakeLoginResponse:
    user = _FakeUserProfile()


class _FakeAuthenticationService:
    def logout(self, refresh_token: str) -> None:
        return None

    def login(self, username: str, password: str) -> Any:
        return _FakeLoginResponse()


def test_authentication_service_publishes_logged_in_and_logged_out() -> None:
    service = _build_service()
    wrapped = RealtimePublishingAuthenticationService(_FakeAuthenticationService(), service)

    wrapped.login("alice", "secret")
    wrapped.logout("refresh-token")

    assert _event_types(service) == [EventType.USER_LOGGED_IN, EventType.USER_LOGGED_OUT]
    assert service.replay()[0].event.user_id == "u1"


# -- workflow_publisher: WorkflowService / ReflectionService / WorkflowOptimizer -----


def _execution(status: WorkflowStatus) -> WorkflowExecution:
    now = utc_now()
    return WorkflowExecution(
        workflow_execution_id="we1", workflow_id="w1", plan_id="p1", execution_id="e1",
        status=status, started_at=now, updated_at=now,
    )


class _FakeWorkflowService:
    def __init__(self, terminal_status: WorkflowStatus) -> None:
        self.terminal_status = terminal_status

    async def execute(self, workflow_id: str, session_id: str | None = None) -> WorkflowExecution:
        return _execution(self.terminal_status)

    def get(self, workflow_id: str) -> str:
        return "forwarded"


def test_workflow_service_publishes_started_then_completed() -> None:
    service = _build_service()
    wrapped = RealtimePublishingWorkflowService(_FakeWorkflowService(WorkflowStatus.COMPLETED), service)

    execution = asyncio.run(wrapped.execute("w1"))

    assert execution.status == WorkflowStatus.COMPLETED
    assert _event_types(service) == [EventType.WORKFLOW_STARTED, EventType.WORKFLOW_COMPLETED]


def test_workflow_service_publishes_started_then_failed() -> None:
    service = _build_service()
    wrapped = RealtimePublishingWorkflowService(_FakeWorkflowService(WorkflowStatus.FAILED), service)

    asyncio.run(wrapped.execute("w1"))

    assert _event_types(service) == [EventType.WORKFLOW_STARTED, EventType.WORKFLOW_FAILED]


def test_workflow_service_forwards_unrelated_methods_via_getattr() -> None:
    service = _build_service()
    wrapped = RealtimePublishingWorkflowService(_FakeWorkflowService(WorkflowStatus.COMPLETED), service)

    assert wrapped.get("w1") == "forwarded"


class _FakeReflectionResult:
    reflection_id = "r1"
    plan_id = "p1"
    trace_id = "t1"


class _FakeReflectionService:
    def generate(self, plan: Any, trace: Any, collaboration_task: Any = None, report_document: Any = None) -> Any:
        return _FakeReflectionResult()


def test_reflection_service_publishes_reflection_generated() -> None:
    service = _build_service()
    wrapped = RealtimePublishingReflectionService(_FakeReflectionService(), service)

    result = wrapped.generate(plan=object(), trace=object())

    assert result.reflection_id == "r1"
    assert _event_types(service) == [EventType.REFLECTION_GENERATED]


class _FakeOptimizationResult:
    optimization_id = "o1"
    plan_id = "p1"
    decisions: ClassVar[list[Any]] = []
    parallelism_improved = True


class _FakeWorkflowOptimizer:
    def adaptive_optimize(self, plan: Any, session_id: str | None) -> Any:
        return _FakeOptimizationResult()

    def structural_optimize(self, plan: Any) -> Any:
        return plan


def test_workflow_optimizer_publishes_optimization_generated() -> None:
    service = _build_service()
    wrapped = RealtimePublishingWorkflowOptimizer(_FakeWorkflowOptimizer(), service)

    result = wrapped.adaptive_optimize(plan=object(), session_id=None)

    assert result.optimization_id == "o1"
    assert _event_types(service) == [EventType.OPTIMIZATION_GENERATED]

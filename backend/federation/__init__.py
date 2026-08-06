"""Federated Multi-Cluster Orchestration & Cloud-Native Coordination.

A pure, additive coordination layer on top of the existing distributed
execution stack (`backend/distributed/`, Phase 38) — none of
Execution/Workflow/Distributed/Planner/Approval/Memory/Observability/
Security/Realtime/Agent logic is modified. A "cluster" here is a real,
independently-tracked registration record (another InsightPilot
deployment, self-registering over REST) — but this process has no
message broker or RPC transport (and adding one was explicitly out of
scope: "no automatic networking or RPC. All communication is
represented as routing decisions only"), so a `RoutingDecision` records
*which cluster the workload is credited to*, never actually ships the
workload anywhere: the real workflow always executes locally, through
the same real `WorkflowService`/`ExecutionService`/`DistributedExecutionService`
Phase 1-38 already built. See `FederationCoordinator`'s own docstring
for the full "why."
"""

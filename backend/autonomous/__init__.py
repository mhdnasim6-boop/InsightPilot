"""Autonomous Optimization & Self-Healing Platform.

A pure, additive analytics layer sitting entirely *outside* every
existing subsystem — Agents/Workflows/Execution/Planning/Distributed/
Federation/Security/Memory/Reflection/Realtime/Observability/Adaptive
Planning/Plugins are never modified, never duplicated. This package only
*reads* each subsystem's own already-computed statistics (``WorkflowService.statistics()``,
``MetricsService.summary()``, ``DistributedExecutionService.cluster_statistics()``,
``FederationService.federation_statistics()``, ``MemoryService.statistics()``,
``ReflectionService.statistics()``, ``AdaptivePlanningService.statistics()``,
...) and turns them into ``Bottleneck``/``OptimizationAction``/
``HealingRecommendation`` findings — never a raw recomputation of
anything those services already aggregate.

**Advisory only, structurally enforced, not just by convention.**
Nothing in this package ever calls a mutating method on any reused
service — every reused collaborator is used exclusively through its own
read-only surface (`.statistics()`, `.list_*()`, `.get_*()`). Every
``HealingRecommendation`` this package can produce has
``requires_human_approval=True`` fixed at the model level (not a default
a caller could override), and ``HealingValidator`` rejects anything that
doesn't hold that invariant before it's ever allowed into a report. See
``AutonomousService``'s own docstring for the full pipeline.
"""

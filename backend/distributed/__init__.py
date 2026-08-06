"""Distributed Execution & Horizontal Scaling layer.

A pure, additive coordination layer on top of the existing single-process
execution stack (``ExecutionService``/``DAGScheduler``/``NodeDispatcher``/
``ExecutionPool``) — none of them are modified. Workers register
themselves (real bookkeeping: a ``Worker`` row, a heartbeat clock, a
lease per assigned task), and ``DispatchScheduler`` decides *which
registered worker is credited with* a step before it runs — but the step
itself still executes in-process, through the same real agent service
Phase 1-37 already built, since this codebase has no message broker or
RPC transport to actually ship work to a separate process. See
``DistributedExecutionService``'s own docstring for the full "why."
"""

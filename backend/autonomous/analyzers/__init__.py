"""Analyzers: read-only threshold rules over each reused service's own statistics.

Every analyzer's ``analyze()`` returns ``(bottlenecks, decision)`` — a
list of ``Bottleneck`` findings plus one ``AutonomousDecision`` summarizing
that analyzer's own overall verdict for this pass. None of these classes
call a mutating method on anything; every one only reads an
already-computed statistics object handed to it by ``AutonomousService``.
"""

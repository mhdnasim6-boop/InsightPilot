"""Optimizer: turns detected Bottlenecks into advisory OptimizationActions.

Nothing here executes anything — every class in this package only
*constructs* ``OptimizationAction``/``HealingRecommendation`` objects
from ``Bottleneck`` findings the analyzers already produced.
"""

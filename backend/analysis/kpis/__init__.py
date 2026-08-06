"""A reusable, configurable KPI engine.

Mirrors ``backend.ai.providers.factory.ProviderFactory``: a dict-based
calculator registry (no if/else chains) that future business KPIs
(Revenue, Profit, Margin, ...) plug into via ``KPIEngine.register()`` —
the engine's own dispatch loop never needs to change.
"""

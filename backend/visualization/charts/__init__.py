"""Chart generators: the ``ChartGenerator`` interface and one implementation
per supported chart type. A future chart type only needs to implement
``ChartGenerator`` and be added to ``registry.default_generators()`` —
nothing else changes.
"""

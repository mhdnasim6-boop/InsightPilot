"""Deterministic chart recommendation: tries every registered ``ChartGenerator``
and keeps the ones applicable to the given ``ChartContext``. No AI — every
decision is a fixed, inspectable rule inside a generator's own
``applicable()`` check (e.g. "a time column exists" -> line chart).
"""

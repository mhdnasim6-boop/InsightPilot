"""Pure, independently testable pandas transformations.

Each ``CleaningRule`` is a thin wrapper (validate/apply/rollback/
description bookkeeping) around one function here — keeping the actual
data mutation logic reusable and testable without the rule contract
around it.
"""

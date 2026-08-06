"""MemoryType: what kind of knowledge a MemoryItem records.

One value per integration point this phase wires up — never a
catch-all "generic" bucket, so every consumer of the memory layer can
filter to exactly the kind of knowledge it cares about.
"""

from enum import Enum


class MemoryType(str, Enum):
    """The kind of knowledge one MemoryItem records."""

    CONVERSATION = "conversation"
    DATASET = "dataset"
    ANALYSIS = "analysis"
    VISUALIZATION = "visualization"
    REPORT = "report"
    EXECUTION = "execution"
    APPROVAL = "approval"
    USER_PREFERENCE = "user_preference"
    DECISION = "decision"
    EXTERNAL_KNOWLEDGE = "external_knowledge"
    COLLABORATION = "collaboration"
    REFLECTION = "reflection"
    ADAPTIVE_PLAN = "adaptive_plan"

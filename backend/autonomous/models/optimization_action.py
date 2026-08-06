"""OptimizationAction: one advisory action suggested for a detected Bottleneck.

Deliberately carries no execution hook of any kind — there is no
``apply()``/``execute()`` method anywhere on this model or anything that
produces it. ``safe_to_automate`` is fixed ``False`` (not a default a
caller could flip) because this phase's own contract is "generate
recommendations only... everything is advisory," made structural rather
than just documented.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.autonomous.models.bottleneck import BottleneckCategory


class OptimizationAction(BaseModel):
    """One suggested, human-reviewed action addressing a specific Bottleneck."""

    model_config = ConfigDict(frozen=True)

    action_id: str
    bottleneck_id: str
    category: BottleneckCategory
    title: str
    description: str
    estimated_impact: Literal["low", "medium", "high"]
    safe_to_automate: Literal[False] = False
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

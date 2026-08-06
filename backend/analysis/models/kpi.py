"""KPI definitions and results.

``KPIType`` covers the generic KPIs this phase implements. Future business
KPIs (Revenue, Profit, Margin, ...) plug into ``KPIEngine`` by adding a new
value here and registering a calculator (``KPIEngine.register()``) — the
engine's dispatch loop never needs to change.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class KPIType(str, Enum):
    """Generic, column-oriented KPI calculations."""

    RECORD_COUNT = "record_count"
    NULL_PERCENTAGE = "null_percentage"
    DISTINCT_COUNT = "distinct_count"
    AVERAGE = "average"
    SUM = "sum"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    MEAN = "mean"
    MEDIAN = "median"


class KPIDefinition(BaseModel):
    """One KPI to compute.

    ``params`` is a free-form escape hatch a future multi-column business
    KPI (e.g. a profit margin ratio) can read from inside its own
    registered calculator, without needing this schema to change.
    """

    name: str
    kpi_type: KPIType
    column: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class KPIResult(BaseModel):
    """The computed value for one KPI definition."""

    name: str
    kpi_type: KPIType
    column: str | None = None
    value: float | int | None = None

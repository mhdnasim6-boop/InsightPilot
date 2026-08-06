"""Computes a configurable set of KPIs against a DataFrame."""

import pandas as pd

from backend.analysis.exceptions.errors import UnknownKPITypeError
from backend.analysis.kpis.calculators import DEFAULT_CALCULATORS, KPICalculator
from backend.analysis.kpis.defaults import default_kpi_definitions
from backend.analysis.models.kpi import KPIDefinition, KPIResult, KPIType


class KPIEngine:
    """Computes ``KPIResult``s for a list of ``KPIDefinition``s (or a sensible default set)."""

    def __init__(self, calculators: dict[KPIType, KPICalculator] | None = None) -> None:
        self._calculators: dict[KPIType, KPICalculator] = dict(DEFAULT_CALCULATORS)
        if calculators:
            self._calculators.update(calculators)

    def register(self, kpi_type: KPIType, calculator: KPICalculator) -> None:
        """Register or override a calculator — how future business KPIs plug into this engine."""
        self._calculators[kpi_type] = calculator

    def compute(self, dataframe: pd.DataFrame, definitions: list[KPIDefinition] | None = None) -> list[KPIResult]:
        """Compute every KPI in ``definitions``, or a sensible default set if none is given."""
        active_definitions = definitions if definitions is not None else default_kpi_definitions(dataframe)
        return [self._compute_one(dataframe, definition) for definition in active_definitions]

    def _compute_one(self, dataframe: pd.DataFrame, definition: KPIDefinition) -> KPIResult:
        calculator = self._calculators.get(definition.kpi_type)
        if calculator is None:
            raise UnknownKPITypeError(f"No calculator registered for KPI type '{definition.kpi_type.value}'.")
        value = calculator(dataframe, definition)
        return KPIResult(name=definition.name, kpi_type=definition.kpi_type, column=definition.column, value=value)

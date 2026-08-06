"""Builds the default KPI set for a dataset when a caller doesn't supply its own.

Null percentage and distinct count are meaningful for any column;
average/sum/min/max/mean/median only make sense for numeric ones.
"""

import pandas as pd

from backend.analysis.models.kpi import KPIDefinition, KPIType


def default_kpi_definitions(dataframe: pd.DataFrame) -> list[KPIDefinition]:
    """Return a sensible default set of KPIDefinitions for ``dataframe``."""
    numeric_columns = set(dataframe.select_dtypes(include="number").columns)

    definitions = [KPIDefinition(name="Record Count", kpi_type=KPIType.RECORD_COUNT)]

    for column in dataframe.columns:
        name = str(column)
        definitions.append(
            KPIDefinition(name=f"{name} Null Percentage", kpi_type=KPIType.NULL_PERCENTAGE, column=name)
        )
        definitions.append(
            KPIDefinition(name=f"{name} Distinct Count", kpi_type=KPIType.DISTINCT_COUNT, column=name)
        )
        if column in numeric_columns:
            definitions.append(KPIDefinition(name=f"{name} Average", kpi_type=KPIType.AVERAGE, column=name))
            definitions.append(KPIDefinition(name=f"{name} Sum", kpi_type=KPIType.SUM, column=name))
            definitions.append(KPIDefinition(name=f"{name} Minimum", kpi_type=KPIType.MINIMUM, column=name))
            definitions.append(KPIDefinition(name=f"{name} Maximum", kpi_type=KPIType.MAXIMUM, column=name))
            definitions.append(KPIDefinition(name=f"{name} Mean", kpi_type=KPIType.MEAN, column=name))
            definitions.append(KPIDefinition(name=f"{name} Median", kpi_type=KPIType.MEDIAN, column=name))

    return definitions

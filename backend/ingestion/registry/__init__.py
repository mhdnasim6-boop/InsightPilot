"""Key-based lookups for the ingestion layer: ``LoaderRegistry`` (extension
-> loader, no if/else chains — mirrors ``backend.ai.providers.factory``)
and ``DataFrameStore`` (dataset_id -> DataFrame, the mechanism behind
``BusinessDataset.dataframe_reference``).
"""

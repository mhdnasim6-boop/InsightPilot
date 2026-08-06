"""Data loaders: the ``DataLoader`` interface and its implementations
(``CSVLoader``, ``ExcelLoader``). A future loader (PDF, SQL, API, ...) only
needs to implement ``DataLoader`` and register in
``backend.ingestion.registry.loader_registry`` — nothing else changes.
"""

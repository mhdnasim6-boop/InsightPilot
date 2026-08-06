"""Storage-agnostic repository layer.

Services depend only on the abstract contracts defined here, never on the
concrete (currently in-memory) implementations directly — that's what
lets a future SQLite/Postgres-backed repository replace the in-memory one
without touching a single line of service or router code.
"""

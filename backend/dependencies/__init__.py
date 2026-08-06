"""FastAPI dependency providers.

Every repository, service, and the job manager is constructed exactly
once, here — routers and services never instantiate them directly.
"""

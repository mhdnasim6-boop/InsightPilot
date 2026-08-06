"""Provider-independent streaming abstraction.

No dependency on FastAPI's ``StreamingResponse`` — a future router can
adapt an ``AIStream`` into one, but the abstraction itself doesn't know
FastAPI exists.
"""

"""Plan lifecycle events and a dedicated ``PlanEventBus``.

Mirrors ``backend.orchestration.events`` (an event-type/EventBus pair)
exactly — plan lifecycle events are a distinct family from graph node
events, so they get their own base type and bus rather than being
shoehorned into the orchestration one.
"""

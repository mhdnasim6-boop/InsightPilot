"""Reusable prompt registration and rendering.

Infrastructure only — this module registers no prompts of its own.
Future business/agent code registers its own prompts against a
``PromptManager`` instance, then renders them by name.
"""

from typing import Any

from backend.ai.exceptions.errors import InvalidPromptError


class PromptManager:
    """Registers named prompt templates and renders them with variables."""

    def __init__(self) -> None:
        self._templates: dict[str, str] = {}

    def register(self, name: str, template: str) -> None:
        """Register a prompt template under a name, overwriting any existing one."""
        if not name or not name.strip():
            raise InvalidPromptError("Prompt name must not be empty.")
        self._templates[name] = template

    def get(self, name: str, /, **variables: Any) -> str:
        """Render a registered prompt template, substituting the given variables.

        ``name`` is positional-only so it can never collide with a
        template variable that happens to be called ``name`` (e.g. a
        template of ``"Hello, {name}!"`` rendered via ``get("greeting",
        name="Ada")``).
        """
        template = self._templates.get(name)
        if template is None:
            raise InvalidPromptError(f"Prompt '{name}' is not registered.")
        try:
            return template.format(**variables)
        except KeyError as exc:
            raise InvalidPromptError(f"Prompt '{name}' is missing variable {exc}.") from exc

    def is_registered(self, name: str) -> bool:
        """Return whether a prompt name has been registered."""
        return name in self._templates

    def list_names(self) -> list[str]:
        """Return all registered prompt names."""
        return sorted(self._templates.keys())

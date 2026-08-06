"""Extracts the first well-formed top-level JSON object from arbitrary text.

Real (and mock) LLM responses may wrap JSON in prose or markdown code
fences; this performs a mechanical brace-matching scan (correctly skipping
braces inside quoted strings) rather than a fragile regex, so it works
regardless of what surrounds the JSON.
"""


def extract_json_object(text: str) -> str:
    """Return the first balanced ``{...}`` substring in ``text``.

    Raises ``ValueError`` if no balanced JSON object is found — callers
    convert that into a domain-specific error.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in the response.")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("No balanced JSON object found in the response.")

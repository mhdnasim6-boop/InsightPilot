"""Deterministic textual similarity — word-overlap (Jaccard) scoring, never an
embedding or vector comparison.

This is the one function a future vector-backed memory implementation
would actually replace: everything above it (``RetrievalEngine``,
``MemoryService``) only ever calls ``word_overlap_score()`` by name, so
swapping it for a real embedding-cosine-similarity function later
touches this file alone — see this package's own top-level docstring.
"""


def _tokenize(text: str) -> set[str]:
    return {token for token in text.lower().split() if token}


def word_overlap_score(a: str, b: str) -> float:
    """Jaccard similarity (intersection / union) between two strings' word sets.

    Returns 0.0 if either string has no words. Purely lexical — this is
    NOT semantic similarity; two sentences with the same meaning but
    different words score 0.0. That tradeoff is intentional per this
    phase's own "no embeddings" constraint.
    """
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)

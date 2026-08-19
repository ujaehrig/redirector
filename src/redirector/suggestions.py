"""Suggestion matching for 404 responses."""

import difflib


def find_suggestions(
    query: str,
    candidates: list[str],
    threshold: float,
    max_results: int,
) -> list[str]:
    """Find similar short codes for a failed lookup.

    Uses substring matching first, then falls back to fuzzy matching
    (difflib) for remaining candidates.

    Args:
        query: The short code that was not found.
        candidates: List of existing short codes to match against.
        threshold: Minimum similarity ratio (0.0-1.0) for fuzzy matches.
        max_results: Maximum number of suggestions to return.

    Returns:
        A list of matching short codes, up to max_results.
    """
    if not query or not candidates:
        return []

    normalized_query = query.lower()
    results: list[str] = []

    # Phase 1: Substring matching
    for candidate in candidates:
        if candidate == normalized_query:
            # Skip exact match — it would have redirected
            continue
        if normalized_query in candidate:
            results.append(candidate)

    # Phase 2: Fuzzy matching for remaining candidates
    if len(results) < max_results:
        already_found = set(results)
        remaining = [
            c for c in candidates if c not in already_found and c != normalized_query
        ]
        fuzzy_matches = difflib.get_close_matches(
            normalized_query,
            remaining,
            n=max_results - len(results),
            cutoff=threshold,
        )
        results.extend(fuzzy_matches)

    return results[:max_results]

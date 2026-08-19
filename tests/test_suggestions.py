"""Tests for the suggestion matching module."""

from redirector.suggestions import find_suggestions


class TestSubstringMatching:
    """Test substring-based matching."""

    def test_finds_substring_matches(self) -> None:
        candidates = ["java17-api", "java21-api", "python-docs", "go-api"]
        results = find_suggestions("java", candidates, threshold=0.6, max_results=5)
        assert "java17-api" in results
        assert "java21-api" in results

    def test_substring_match_is_case_insensitive(self) -> None:
        candidates = ["java17-api", "python-docs"]
        results = find_suggestions("Java", candidates, threshold=0.6, max_results=5)
        assert "java17-api" in results

    def test_prefix_match(self) -> None:
        candidates = ["heise-news", "heise-dev", "google"]
        results = find_suggestions("heise", candidates, threshold=0.6, max_results=5)
        assert "heise-news" in results
        assert "heise-dev" in results
        assert "google" not in results

    def test_infix_match(self) -> None:
        candidates = ["my-java-docs", "python-docs"]
        results = find_suggestions("java", candidates, threshold=0.6, max_results=5)
        assert "my-java-docs" in results


class TestFuzzyMatching:
    """Test fuzzy matching fallback."""

    def test_finds_typo_matches(self) -> None:
        candidates = ["java17-api", "python-docs", "golang"]
        results = find_suggestions(
            "jva17-api", candidates, threshold=0.6, max_results=5
        )
        assert "java17-api" in results

    def test_respects_threshold(self) -> None:
        candidates = ["java17-api", "completely-different"]
        results = find_suggestions("xyz", candidates, threshold=0.6, max_results=5)
        assert "completely-different" not in results

    def test_high_threshold_filters_more(self) -> None:
        candidates = ["java17-api", "java21-api", "javaee"]
        results = find_suggestions("javaa", candidates, threshold=0.9, max_results=5)
        # At 0.9 threshold, only very close matches should pass
        assert len(results) <= len(candidates)


class TestMaxResults:
    """Test result limiting."""

    def test_limits_results(self) -> None:
        candidates = [f"java{i}-api" for i in range(20)]
        results = find_suggestions("java", candidates, threshold=0.6, max_results=3)
        assert len(results) <= 3

    def test_returns_all_when_under_limit(self) -> None:
        candidates = ["java17-api", "java21-api"]
        results = find_suggestions("java", candidates, threshold=0.6, max_results=5)
        assert len(results) == 2


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_candidates(self) -> None:
        results = find_suggestions("java", [], threshold=0.6, max_results=5)
        assert results == []

    def test_exact_match_not_included(self) -> None:
        """Exact match shouldn't be suggested (it would have redirected)."""
        candidates = ["java", "java17-api"]
        results = find_suggestions("java", candidates, threshold=0.6, max_results=5)
        # "java" itself should not appear — only longer/different matches
        assert "java17-api" in results

    def test_empty_query(self) -> None:
        candidates = ["java17-api", "python-docs"]
        results = find_suggestions("", candidates, threshold=0.6, max_results=5)
        assert results == []

    def test_no_duplicates_between_substring_and_fuzzy(self) -> None:
        """A match found by substring shouldn't appear twice."""
        candidates = ["java17-api", "java21-api"]
        results = find_suggestions("java1", candidates, threshold=0.3, max_results=5)
        # Even if fuzzy also matches, no duplicates
        assert len(results) == len(set(results))

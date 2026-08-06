"""Tests for QuestionClassifier — deterministic keyword-based intent classification."""

import pytest

from backend.chatbot.retrieval.classifier import Intent, QuestionClassifier


@pytest.mark.parametrize(
    ("question", "expected_intent"),
    [
        ("Can you give me a summary of this dataset?", Intent.SUMMARY),
        ("Give me an overview", Intent.SUMMARY),
        ("What are the key KPIs?", Intent.KPI),
        ("What's the average revenue?", Intent.KPI),
        ("What is the trend for revenue over time?", Intent.TREND),
        ("Is revenue increasing?", Intent.TREND),
        ("Compare East versus West", Intent.COMPARISON),
        ("What's the difference between these two regions?", Intent.COMPARISON),
        ("Are there any anomalies in this data?", Intent.ANOMALY),
        ("Show me the outliers", Intent.ANOMALY),
        ("What correlates with revenue?", Intent.CORRELATION),
        ("Is cost related to revenue?", Intent.CORRELATION),
        ("Why is West revenue so high?", Intent.EXPLANATION),
        ("Can you explain this finding?", Intent.EXPLANATION),
        ("Show me a chart of revenue", Intent.VISUALIZATION),
        ("Can you plot this?", Intent.VISUALIZATION),
        ("What should I do next?", Intent.PLANNING),
        ("What's your recommended next step?", Intent.PLANNING),
        ("Can you summarize this report?", Intent.REPORT),
        ("What's in the executive summary?", Intent.REPORT),
        ("What's the status of this workflow?", Intent.WORKFLOW),
        ("Tell me about this pipeline run", Intent.WORKFLOW),
        ("How did that go?", Intent.REFLECTION),
        ("What are the lessons learned?", Intent.REFLECTION),
        ("What did the optimizer suggest?", Intent.OPTIMIZATION),
        ("How was this plan optimized?", Intent.OPTIMIZATION),
        ("hello", Intent.GENERAL),
        ("what can you do?", Intent.GENERAL),
    ],
)
def test_classify_matches_expected_intent(question: str, expected_intent: Intent) -> None:
    classifier = QuestionClassifier()
    assert classifier.classify(question) == expected_intent


def test_classify_is_case_insensitive() -> None:
    classifier = QuestionClassifier()
    assert classifier.classify("WHAT ARE THE KEY METRICS?") == Intent.KPI


def test_classify_falls_back_to_general_for_unmatched_text() -> None:
    classifier = QuestionClassifier()
    assert classifier.classify("asdf qwerty zzz") == Intent.GENERAL

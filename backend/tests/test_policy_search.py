from dataclasses import asdict

import pytest

from app.policies import load_policy_sections, search_policy


def test_all_policies_load_as_heading_sections() -> None:
    sections = load_policy_sections()
    assert {section.policy_type for section in sections} == {
        "refund",
        "return",
        "shipping",
    }
    assert all(section.section_title and section.content for section in sections)
    assert {section.source_path for section in sections} == {
        "refund_policy.md",
        "return_policy.md",
        "shipping_policy.md",
    }


@pytest.mark.parametrize("query", ["", "   ", "---"])
def test_empty_query_is_rejected(query: str) -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        search_policy(query)


def test_invalid_policy_type_and_limit_are_rejected() -> None:
    with pytest.raises(ValueError, match="policy_type"):
        search_policy("refund", "payments")
    with pytest.raises(ValueError, match="limit must be between 1 and 10"):
        search_policy("refund", limit=0)
    with pytest.raises(ValueError, match="limit must be between 1 and 10"):
        search_policy("refund", limit=11)


@pytest.mark.parametrize(
    ("query", "expected_type", "expected_section"),
    [
        ("defective item refund", "refund", "Defective or Damaged Items"),
        ("size issue return", "return", "Size-Related Returns"),
        ("damaged shipment", "shipping", "Lost or Damaged Shipments"),
        ("refund processing time", "refund", "Refund Processing"),
    ],
)
def test_relevant_section_ranks_first(
    query: str, expected_type: str, expected_section: str
) -> None:
    results = search_policy(query)
    assert results
    assert results[0].policy_type == expected_type
    assert results[0].section_title == expected_section


def test_filter_no_match_and_ordering_are_deterministic() -> None:
    first = [asdict(result) for result in search_policy("delivery refund", limit=10)]
    second = [asdict(result) for result in search_policy("delivery refund", limit=10)]
    assert first == second
    assert search_policy("quasar nebula", "refund") == []
    assert all(
        result.policy_type == "shipping"
        for result in search_policy("delivery", "shipping")
    )

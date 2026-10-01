import re

from app.policies.loader import load_policy_sections
from app.policies.models import PolicySearchResult, PolicySection, PolicyType

VALID_POLICY_TYPES = frozenset({"refund", "return", "shipping"})
MIN_LIMIT = 1
MAX_LIMIT = 10
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def search_policy(
    query: str,
    policy_type: str | None = None,
    limit: int = 5,
) -> list[PolicySearchResult]:
    normalized_query = " ".join(_tokens(query))
    if not normalized_query:
        raise ValueError("query must not be empty")
    if policy_type is not None and policy_type not in VALID_POLICY_TYPES:
        raise ValueError("policy_type must be one of: refund, return, shipping")
    if not MIN_LIMIT <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")

    query_tokens = set(normalized_query.split())
    matches: list[PolicySearchResult] = []
    for section in load_policy_sections():
        if policy_type is not None and section.policy_type != policy_type:
            continue
        score = _score(section, normalized_query, query_tokens)
        if score == 0:
            continue
        matches.append(
            PolicySearchResult(
                policy_type=section.policy_type,
                policy_name=section.policy_name,
                section_title=section.section_title,
                content=section.content,
                score=score,
                source_path=section.source_path,
            )
        )

    matches.sort(
        key=lambda result: (
            -result.score,
            result.policy_type,
            result.section_title.lower(),
            result.source_path,
        )
    )
    return matches[:limit]


def _score(
    section: PolicySection, normalized_query: str, query_tokens: set[str]
) -> int:
    title = " ".join(_tokens(section.section_title))
    body = " ".join(_tokens(section.content))
    title_tokens = set(title.split())
    body_tokens = set(body.split())
    score = 0
    if normalized_query in title:
        score += 100
    if normalized_query in body:
        score += 50
    score += 10 * len(query_tokens & title_tokens)
    score += len(query_tokens & body_tokens)
    return score


def _tokens(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())

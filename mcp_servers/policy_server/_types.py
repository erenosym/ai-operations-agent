from typing import TypedDict


class PolicySearchOutput(TypedDict):
    policy_type: str
    policy_name: str
    section_title: str
    content: str
    score: int
    source: str


class PolicySearchResponse(TypedDict):
    results: list[PolicySearchOutput]

from dataclasses import dataclass
from typing import Literal

PolicyType = Literal["refund", "return", "shipping"]


@dataclass(frozen=True)
class PolicySection:
    policy_type: PolicyType
    policy_name: str
    section_title: str
    content: str
    source_path: str


@dataclass(frozen=True)
class PolicySearchResult:
    policy_type: PolicyType
    policy_name: str
    section_title: str
    content: str
    score: int
    source_path: str

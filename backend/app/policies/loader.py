from pathlib import Path
import re

from app.policies.models import PolicySection, PolicyType

POLICY_FILES: tuple[tuple[PolicyType, str], ...] = (
    ("refund", "refund_policy.md"),
    ("return", "return_policy.md"),
    ("shipping", "shipping_policy.md"),
)
HEADING_PATTERN = re.compile(r"^(#{1,2})\s+(.+?)\s*$")


def default_policy_directory() -> Path:
    return Path(__file__).resolve().parents[3] / "policies"


def load_policy_sections(policy_directory: Path | None = None) -> tuple[PolicySection, ...]:
    directory = policy_directory or default_policy_directory()
    sections: list[PolicySection] = []
    for policy_type, filename in POLICY_FILES:
        path = directory / filename
        sections.extend(_parse_policy(path, policy_type))
    return tuple(sections)


def _parse_policy(path: Path, policy_type: PolicyType) -> list[PolicySection]:
    policy_name: str | None = None
    section_title: str | None = None
    body: list[str] = []
    parsed: list[PolicySection] = []

    def append_section() -> None:
        if policy_name is None or section_title is None:
            return
        content = "\n".join(body).strip()
        if not content:
            raise ValueError(f"Policy section '{section_title}' in {path.name} is empty")
        parsed.append(
            PolicySection(
                policy_type=policy_type,
                policy_name=policy_name,
                section_title=section_title,
                content=content,
                source_path=path.name,
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading and heading.group(1) == "#":
            policy_name = heading.group(2)
            continue
        if heading and heading.group(1) == "##":
            append_section()
            section_title = heading.group(2)
            body = []
            continue
        if section_title is not None:
            body.append(line)
    append_section()

    if policy_name is None or not parsed:
        raise ValueError(f"Policy file {path.name} must have a title and sections")
    return parsed

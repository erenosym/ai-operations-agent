# Repository Guidelines

- Avoid unnecessary abstractions; implement the smallest clear solution.
- Prefer typed interfaces at module and service boundaries.
- Never expose unrestricted arbitrary SQL execution as an agent tool.
- Add or update tests whenever behavior changes.
- Never commit secrets; use environment variables and `.env.example`.
- Update architecture documentation when major system boundaries change.
- Run relevant tests and lint checks before considering work complete.

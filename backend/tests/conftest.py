import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://unit-test-user:unit-test-password@invalid:5432/unit-test",
)

import asyncio

from app.database.engine import check_database_connection, engine


async def main() -> None:
    try:
        await check_database_connection()
        print("Database connectivity check passed: SELECT 1")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

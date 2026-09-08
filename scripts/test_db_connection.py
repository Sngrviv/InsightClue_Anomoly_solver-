"""
Verification script for InsightClue database, pgvector, and Redis cache.
Runs async connectivity tests and vector similarity calculations.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root directory to sys.path so 'src' can be imported cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 stdout on Windows terminals
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from redis.asyncio import Redis
from sqlalchemy import text
from src.config.settings import get_settings
from src.database.session import AsyncSessionFactory, async_engine


async def test_postgres_and_pgvector() -> bool:
    print("\n🔍 [1/2] Testing PostgreSQL + pgvector Connectivity...")
    settings = get_settings()
    print(f"    Connecting to: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

    try:
        async with AsyncSessionFactory() as session:
            # 1. Test basic database connection
            result = await session.execute(text("SELECT version();"))
            pg_version = result.scalar()
            print(f"    ✅ Connected to PostgreSQL! Version: {pg_version[:45]}...")

            # 2. Ensure pgvector extension is enabled
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await session.commit()
            print("    ✅ 'vector' extension is active and verified.")

            # 3. Test Vector Operations in Postgres
            await session.execute(
                text(
                    """
                    CREATE TEMP TABLE IF NOT EXISTS _test_vectors (
                        id serial PRIMARY KEY,
                        embedding vector(3)
                    );
                    """
                )
            )
            await session.execute(
                text(
                    """
                    INSERT INTO _test_vectors (embedding) VALUES 
                    ('[1.0, 0.0, 0.0]'),
                    ('[0.0, 1.0, 0.0]'),
                    ('[0.9, 0.1, 0.0]');
                    """
                )
            )
            await session.commit()

            # Query cosine distance: <=> operator
            query = text(
                """
                SELECT id, embedding, embedding <=> '[1.0, 0.0, 0.0]' AS cosine_distance
                FROM _test_vectors
                ORDER BY cosine_distance ASC;
                """
            )
            res = await session.execute(query)
            rows = res.fetchall()

            print("    ✅ Vector similarity query executed successfully:")
            for r in rows:
                print(f"       - Vector ID {r[0]}: {r[1]} -> Cosine Distance: {r[2]:.4f}")

        return True
    except Exception as e:
        print(f"    ❌ PostgreSQL / pgvector error: {e}")
        return False


async def test_redis() -> bool:
    print("\n🔍 [2/2] Testing Redis Cache Connectivity...")
    settings = get_settings()
    print(f"    Connecting to: {settings.REDIS_HOST}:{settings.REDIS_PORT} (DB {settings.REDIS_DB})")

    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        # Test ping
        pong = await redis_client.ping()
        print(f"    ✅ Redis PING -> Response: {pong}")

        # Test set / get
        await redis_client.set("insightclue:healthcheck", "OK", ex=60)
        cached_val = await redis_client.get("insightclue:healthcheck")
        print(f"    ✅ Redis Cache Key 'insightclue:healthcheck' -> Value: '{cached_val}'")

        await redis_client.aclose()
        return True
    except Exception as e:
        print(f"    ❌ Redis error: {e}")
        return False


async def main() -> None:
    print("=" * 60)
    print("🚀 InsightClue Infrastructure Diagnostic Check")
    print("=" * 60)

    pg_ok = await test_postgres_and_pgvector()
    redis_ok = await test_redis()

    await async_engine.dispose()

    print("\n" + "=" * 60)
    if pg_ok and redis_ok:
        print("🎉 ALL CHECKS PASSED: PostgreSQL + pgvector + Redis are ready!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("⚠️ Some infrastructure checks failed. Please check container logs.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import asyncpg
import os
from app.core.config import settings


async def seed_database():
    print(f"🌱 Seeding database at {settings.DATABASE_HOST}...")

    # Read the SQL file



if __name__ == "__main__":
    # Ensure we are running in an async context
    asyncio.run(seed_database())
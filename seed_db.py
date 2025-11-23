import asyncio
import asyncpg
import os
from app.core.config import settings


async def seed_database():
    print(f"🌱 Seeding database at {settings.DATABASE_HOST}...")

    # Read the SQL file
    try:
        with open("seed.sql", "r") as f:
            sql = f.read()
    except FileNotFoundError:
        print("❌ Error: 'seed.sql' file not found.")
        return

    try:
        # Connect using the App User (or Superuser if needed for global tables)
        conn = await asyncpg.connect(settings.DATABASE_URL)

        # Execute the seed script
        # Note: 'permissions' table writes are allowed for app user via
        # the 'allow_system_insert' policy we added in schema.sql
        await conn.execute(sql)

        print("✅ Permissions and static data seeded successfully.")

    except Exception as e:
        print(f"❌ Database Error: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()


if __name__ == "__main__":
    # Ensure we are running in an async context
    asyncio.run(seed_database())
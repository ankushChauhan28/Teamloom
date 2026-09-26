import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_all():
    for db_name in ['employee_task_db', 'practice_db', 'postgres']:
        engine = create_async_engine(f'postgresql+asyncpg://postgres:root@localhost:5432/{db_name}')
        try:
            async with engine.connect() as conn:
                tbl_check = await conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users');"))
                exists = tbl_check.scalar()
                if exists:
                    res = await conn.execute(text("SELECT COUNT(*) FROM users;"))
                    count = res.scalar()
                    print(f"=== DB: {db_name} has users table with {count} rows ===")
                    users = await conn.execute(text("SELECT id, employee_code, full_name, email, access_level, is_active, designation FROM users ORDER BY id;"))
                    for u in users.fetchall():
                        print(f"  {u}")
                    stats = await conn.execute(text("""
                        SELECT COUNT(*) as total_users,
                               SUM(CASE WHEN is_active=true THEN 1 ELSE 0 END) as active_users,
                               SUM(CASE WHEN is_active=false THEN 1 ELSE 0 END) as inactive_users
                        FROM users;
                    """))
                    print(f"  Stats: {stats.fetchone()}")
                else:
                    print(f"=== DB: {db_name} does NOT have a users table ===")
        except Exception as e:
            print(f"DB {db_name} error: {e}")
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_all())

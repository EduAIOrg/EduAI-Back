import asyncio
from sqlalchemy import text
from app.database import engine

async def inspect():
    async with engine.connect() as conn:
        # Get tables
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
        tables = [row[0] for row in res.fetchall()]
        print("TABLES IN DB:", tables)
        
        # Check users columns
        if 'users' in tables:
            res = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users';"))
            print("USERS COLUMNS:", res.fetchall())
            
        # Check documents columns
        if 'documents' in tables:
            res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='documents';"))
            print("DOCUMENTS COLUMNS:", [r[0] for r in res.fetchall()])

async def main():
    await inspect()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

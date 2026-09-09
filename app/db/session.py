from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.db.models import Base
db_url=settings.database_url
if db_url.startswith('postgres://'): db_url='postgresql+asyncpg://'+db_url[len('postgres://'):]
elif db_url.startswith('postgresql://'): db_url='postgresql+asyncpg://'+db_url[len('postgresql://'):]
engine = create_async_engine(db_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from sqlalchemy import select
    from app.db.models import Plan, PlanPeriod
    async with Session() as s:
        count=await s.scalar(select(__import__('sqlalchemy').func.count(Plan.id)))
        if not count:
            p1=Plan(name='INFERIO START',description='Базовый доступ',squad_uuids=[]); p2=Plan(name='INFERIO PRO',description='Default + Bypass',squad_uuids=[]); s.add_all([p1,p2]); await s.flush(); s.add_all([PlanPeriod(plan_id=p1.id,days=30,price=89),PlanPeriod(plan_id=p2.id,days=30,price=200)]); await s.commit()

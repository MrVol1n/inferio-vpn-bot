import asyncio,os
from fastapi import FastAPI,Header,HTTPException
from aiogram import Bot
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.db.session import init_db,Session
from app.db.models import Payment
from app.services.billing import provision_payment
from app.services.platega import PlategaClient
app=FastAPI(title=settings.app_name)
@app.get('/')
async def root(): return {'service':settings.app_name,'status':'ok'}
@app.get('/health')
async def health(): return {'status':'ok'}
@app.get('/payment/return')
async def payment_return(): return {'ok':True,'message':'Вернитесь в Telegram.'}
@app.post('/webhooks/platega')
async def platega_webhook(payload:dict,x_merchantid:str|None=Header(None),x_secret:str|None=Header(None)):
    if x_merchantid!=settings.platega_merchant_id or x_secret!=settings.platega_secret: raise HTTPException(401,'invalid credentials')
    tx=str(payload.get('id') or payload.get('transactionId') or '');status=str(payload.get('status') or '').upper()
    if not tx: raise HTTPException(400,'missing id')
    async with Session() as s:
        p=(await s.execute(select(Payment).where(Payment.transaction_id==tx))).scalar_one_or_none()
        if not p:return {'ok':True}
        if status=='CONFIRMED' and p.status!='COMPLETED':
            bot=Bot(settings.bot_token);await provision_payment(s,p.id,bot);await bot.session.close()
        elif status in ('CANCELED','CHARGEBACKED'): p.status=status;await s.commit()
    return {'ok':True}
async def worker():
    from app.bot import build_dispatcher
    from app.scheduler.jobs import run_expiration
    await init_db();bot=Bot(settings.bot_token);dp=build_dispatcher();sch=AsyncIOScheduler(timezone=settings.timezone);sch.add_job(run_expiration,'interval',minutes=10,args=[bot],id='expiry',replace_existing=True);sch.start()
    try: await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
    finally: sch.shutdown(wait=False);await bot.session.close()
if __name__=='__main__':
    if os.getenv('SERVICE_ROLE','web')=='worker': asyncio.run(worker())
    else:
        import uvicorn;asyncio.run(init_db());uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT','10000')))

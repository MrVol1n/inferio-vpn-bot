from datetime import datetime,timezone
from aiogram import Router,F
from aiogram.types import CallbackQuery
from aiogram.fsm.state import StatesGroup,State
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.bot.keyboards import plans,periods,pay,K,back
from app.db.session import Session
from app.db.models import Plan,PlanPeriod,User,Payment,Subscription
from app.services.billing import calc_price,provision_payment
from app.services.platega import PlategaClient
from app.config import settings
router=Router()
class PromoState(StatesGroup): waiting=State()
@router.callback_query(F.data=='buy')
async def buy(c):
    async with Session() as s: ps=(await s.execute(select(Plan).where(Plan.active==True).order_by(Plan.id))).scalars().all()
    await c.message.answer('🛒 <b>Выберите тариф</b>',reply_markup=plans(ps));await c.answer()
@router.callback_query(F.data.startswith('plan:'))
async def choose_plan(c):
    pid=int(c.data.split(':')[1])
    async with Session() as s:p=(await s.execute(select(Plan).where(Plan.id==pid,Plan.active==True))).scalar_one();items=(await s.execute(select(PlanPeriod).where(PlanPeriod.plan_id==pid,PlanPeriod.active==True).order_by(PlanPeriod.days))).scalars().all()
    await c.message.answer(f'<b>{p.name}</b>\n{p.description}\n\nВыберите срок:',reply_markup=periods(p,items));await c.answer()
@router.callback_query(F.data.startswith('period:'))
async def pick(c,state):
    _,pid,perid=c.data.split(':');pid=int(pid);perid=int(perid)
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one();p=(await s.execute(select(Plan).where(Plan.id==pid))).scalar_one();pr=(await s.execute(select(PlanPeriod).where(PlanPeriod.id==perid))).scalar_one();price,_=await calc_price(s,u,p,pr,None)
    await state.update_data(plan_id=pid,period_id=perid);await c.message.answer(f'📦 {p.name}\nСрок: {pr.days} дн.\nЦена: <b>{price} ₽</b>',reply_markup=K([[('🎁 Промокод','enterpromo')],[('💳 К оплате','checkout')],[('⬅️ Назад','buy')]]));await c.answer()
@router.callback_query(F.data=='enterpromo')
async def enterpromo(c,state): await state.set_state(PromoState.waiting);await c.message.answer('Введите промокод:');await c.answer()
@router.message(PromoState.waiting)
async def promo(m,state):
    d=await state.get_data();code=m.text.strip().upper()
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one();p=(await s.execute(select(Plan).where(Plan.id==d['plan_id']))).scalar_one();pr=(await s.execute(select(PlanPeriod).where(PlanPeriod.id==d['period_id']))).scalar_one();price,pobj=await calc_price(s,u,p,pr,code)
    if not pobj: await m.answer('❌ Промокод не подходит.');return
    await state.update_data(promo=pobj.code);await state.set_state(None);await m.answer(f'✅ {pobj.code} применён. Итог: <b>{price} ₽</b>',reply_markup=K([[('💳 К оплате','checkout')],[('⬅️ К покупкам','buy')]]))
@router.callback_query(F.data=='checkout')
async def checkout(c,state):
    d=await state.get_data()
    if not d.get('plan_id'): await c.answer('Выберите тариф');return
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one();p=(await s.execute(select(Plan).where(Plan.id==d['plan_id']))).scalar_one();pr=(await s.execute(select(PlanPeriod).where(PlanPeriod.id==d['period_id']))).scalar_one();price,promo=await calc_price(s,u,p,pr,d.get('promo'))
        if price<=0:
            payment=Payment(user_id=u.id,plan_id=p.id,period_id=pr.id,original_amount=pr.price,amount=price,promo_code=promo.code if promo else None,status='PENDING',metadata_json={});s.add(payment);await s.flush();await s.commit();
            bot=__import__('aiogram').Bot(settings.bot_token);await provision_payment(s,payment.id,bot);await bot.session.close();await c.message.answer('✅ Подписка выдана бесплатно.');await state.clear();return
        payment=Payment(user_id=u.id,plan_id=p.id,period_id=pr.id,original_amount=pr.price,amount=price,promo_code=promo.code if promo else None,status='PENDING',metadata_json={});s.add(payment);await s.flush();resp=await PlategaClient().create_payment(price,f'INFERIO {p.name} / {pr.days} дней',f'payment:{payment.id}',u.username,u.telegram_id);payment.transaction_id=resp.get('transactionId') or resp.get('id');payment.payment_url=resp.get('url') or resp.get('paymentUrl');await s.commit();url=payment.payment_url;pid=payment.id
    await c.message.answer(f'💳 К оплате: <b>{price} ₽</b>\n\nСсылка действительна по правилам Platega.',reply_markup=pay(url,pid));await state.clear();await c.answer()
@router.callback_query(F.data.startswith('checkpay:'))
async def checkpay(c):
    pid=int(c.data.split(':')[1])
    async with Session() as s:
        p=(await s.execute(select(Payment).where(Payment.id==pid))).scalar_one();uid=(await s.execute(select(User.id).where(User.telegram_id==c.from_user.id))).scalar_one()
        if p.user_id!=uid: await c.answer('Недоступно');return
        if p.status=='COMPLETED': await c.answer('Уже оплачено');return
        try:
            r=await PlategaClient().get_transaction(p.transaction_id);status=str(r.get('status') or '').upper()
            if status=='CONFIRMED':
                bot=__import__('aiogram').Bot(settings.bot_token);await provision_payment(s,p.id,bot);await bot.session.close();await c.message.answer('✅ Оплата подтверждена, подписка активирована.')
            else: await c.answer(f'Статус: {status or "PENDING"}')
        except: await c.answer('Проверка временно недоступна')
@router.callback_query(F.data=='me')
async def me(c):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one();sub=(await s.execute(select(Subscription).where(Subscription.user_id==u.id,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first();payments=(await s.execute(select(Payment).where(Payment.user_id==u.id,Payment.status=='COMPLETED'))).scalars().all()
    if not sub: await c.message.answer(f'У вас нет активной подписки. Покупок: {len(payments)}',reply_markup=back());return
    left=max(0,(sub.expires_at-datetime.now(timezone.utc)).days);await c.message.answer(f'👤 <b>Моя подписка</b>\n\nДо: <b>{sub.expires_at.astimezone().strftime("%d.%m.%Y %H:%M")}</b>\nОсталось: {left} дн.\nПокупок: {len(payments)}',reply_markup=K([[('🔗 Подключение','connect'),('🛒 Продлить','buy')],[('⬅️ Назад','home')]]))
@router.callback_query(F.data=='connect')
async def connect(c):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one();sub=(await s.execute(select(Subscription).where(Subscription.user_id==u.id,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first()
    if not sub: await c.message.answer('Нет активной подписки.',reply_markup=back());return
    await c.message.answer('🔗 <b>Ваша subscription-ссылка</b>\n\n<code>'+str(sub.subscription_url or 'Ссылка пока не получена из Remnawave.')+'</code>\n\nКлиенты: v2rayN / v2rayNG / Hiddify и другие совместимые приложения.',reply_markup=K([[('🪟 v2rayN','https://github.com/2dust/v2rayN/releases'),('🤖 v2rayNG','https://github.com/2dust/v2rayNG/releases')],[('🍎 Hiddify','https://hiddify.com/'),('⬅️ Назад','home')]]))

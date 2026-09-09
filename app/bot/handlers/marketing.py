from aiogram import Router,F
from aiogram.types import CallbackQuery
from sqlalchemy import select,func
from app.db.session import Session
from app.db.models import User,Referral,Payment
from app.bot.keyboards import back
router=Router()
@router.callback_query(F.data=='ref')
async def ref(c):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one();cnt=await s.scalar(select(func.count(Referral.id)).where(Referral.referrer_id==u.id));paid=await s.scalar(select(func.count(Payment.id)).join(User,Payment.user_id==User.id).where(User.referred_by_id==u.id,Payment.status=='COMPLETED'))
    me=await c.bot.get_me();link=f'https://t.me/{me.username}?start=ref_{u.referral_code}'
    await c.message.answer(f'👥 <b>Рефералы</b>\n\nСсылка:\n<code>{link}</code>\n\nПриглашено: {cnt}\nПокупок приглашённых: {paid}\nБонус по умолчанию: +{__import__("app.config",fromlist=["settings"]).settings.referral_reward_days} дней.',reply_markup=back());await c.answer()
@router.callback_query(F.data=='promo')
async def promo(c): await c.message.answer('🎁 Промокод вводится в процессе покупки.',reply_markup=back());await c.answer()

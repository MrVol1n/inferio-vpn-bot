from uuid import uuid4
import os
from aiogram import Router
from aiogram.types import Message,CallbackQuery,FSInputFile
from aiogram.filters import CommandStart
from sqlalchemy import select
from app.db.session import Session
from app.db.models import User,Referral,Partner
from app.config import settings
from app.bot.keyboards import K,main
router=Router()
async def get_or_create_user(tg):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==tg.id))).scalar_one_or_none()
        if not u: u=User(telegram_id=tg.id,username=tg.username,first_name=tg.first_name,last_name=tg.last_name,referral_code=uuid4().hex[:10]);s.add(u);await s.commit()
        else: u.username=tg.username;u.first_name=tg.first_name;u.last_name=tg.last_name;await s.commit()
        return u
async def show_home(target):
    text='🔐 <b>INFERIO VPN</b>\n\nВыберите действие:';kb=main(target.from_user.id in settings.admin_id_set);path='/app/assets/welcome.jpg'
    if isinstance(target,Message):
        if os.path.exists(path): await target.answer_photo(FSInputFile(path),caption=text,reply_markup=kb)
        else: await target.answer(text,reply_markup=kb)
    else:
        if os.path.exists(path): await target.message.answer_photo(FSInputFile(path),caption=text,reply_markup=kb)
        else: await target.message.answer(text,reply_markup=kb)
@router.message(CommandStart())
async def start(m):
    u=await get_or_create_user(m.from_user);arg=(m.text.split(maxsplit=1)[1] if len(m.text.split(maxsplit=1))>1 else '')
    async with Session() as s:
        if arg.startswith('ref_') and not u.referred_by_id:
            r=(await s.execute(select(User).where(User.referral_code==arg[4:]))).scalar_one_or_none()
            if r and r.id!=u.id: u.referred_by_id=r.id;s.add(Referral(referrer_id=r.id,invited_id=u.id))
        if arg.startswith('partner_') and not u.partner_id:
            p=(await s.execute(select(Partner).where(Partner.code==arg[8:],Partner.active==True))).scalar_one_or_none()
            if p: u.partner_id=p.id;p.clicks+=1;p.registrations+=1
        await s.commit()
    if not u.accepted_terms or not u.accepted_privacy:
        await m.answer('👋 <b>INFERIO VPN</b>\n\nПеред использованием примите документы.',reply_markup=K([[('📜 Соглашение','terms'),('🔒 Политика','privacy')],[('✅ Принять','accept')]]));return
    await show_home(m)
@router.callback_query(lambda c:c.data=='accept')
async def accept(c):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one();u.accepted_terms=True;u.accepted_privacy=True;u.terms_version=settings.terms_version;u.privacy_version=settings.privacy_version;await s.commit()
    await c.answer('Принято');await show_home(c)

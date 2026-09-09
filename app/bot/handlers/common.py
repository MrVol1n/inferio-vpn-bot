from datetime import datetime,timezone,timedelta
from aiogram import Router,F
from aiogram.types import CallbackQuery,Message
from aiogram.fsm.state import State,StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from app.config import settings
from app.db.session import Session
from app.db.models import User,Subscription,Ticket,TicketMessage
from app.bot.keyboards import back,K,main
from app.services.remnawave import RemnawaveClient
router=Router()
class SupportState(StatesGroup): waiting=State()
@router.callback_query(F.data=='home')
async def home(c):
    from app.bot.handlers.start import show_home
    await show_home(c);await c.answer()
@router.callback_query(F.data=='terms')
async def terms(c): await c.message.answer(settings.terms_text,reply_markup=back());await c.answer()
@router.callback_query(F.data=='privacy')
async def privacy(c): await c.message.answer(settings.privacy_text,reply_markup=back());await c.answer()
@router.callback_query(F.data=='trial')
async def trial(c):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one()
        if not settings.trial_enabled: await c.answer('Trial отключён');return
        if u.trial_used: await c.answer('Trial уже использован');return
        now=datetime.now(timezone.utc);end=now+timedelta(days=settings.trial_days)
        sub=Subscription(user_id=u.id,started_at=now,expires_at=end,squad_uuids=settings.trial_squads);s.add(sub);u.trial_used=True;await s.commit()
        try:
            rw=RemnawaveClient();ru=await rw.find_user_by_telegram_id(u.telegram_id)
            if isinstance(ru,dict) and ru.get('uuid'): await rw.update_user(ru['uuid'],end,settings.trial_squads)
            else:
                ru=await rw.create_user(f'tg_{u.telegram_id}',end,u.telegram_id,settings.trial_squads);sub.remnawave_user_uuid=ru.get('uuid');
                info=await rw.get_subscription_by_uuid(sub.remnawave_user_uuid);sub.subscription_url=info.get('subscriptionUrl') if isinstance(info,dict) else None;await s.commit()
        except Exception as e:
            await c.message.answer('⚠️ Trial создан в боте, но синхронизация с Remnawave не прошла. Проверьте настройки.');await c.answer();return
    await c.message.answer(f'🎁 Trial активирован на {settings.trial_days} дней.');await c.answer()
@router.callback_query(F.data=='support')
async def support(c,state:FSMContext): await state.set_state(SupportState.waiting);await c.message.answer('💬 Опишите проблему одним сообщением.');await c.answer()
@router.message(SupportState.waiting)
async def support_message(m:Message,state:FSMContext):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one();t=Ticket(user_id=u.id);s.add(t);await s.flush();s.add(TicketMessage(ticket_id=t.id,author_telegram_id=m.from_user.id,text=m.text));await s.commit()
        for admin in settings.admin_id_set:
            try: await m.bot.send_message(admin,f'🆘 Новый тикет #{t.id} от @{u.username or "-"} ({u.telegram_id})\n\n{m.text}\n\nОтвет: /reply {t.id} текст')
            except: pass
    await state.clear();await m.answer(f'✅ Тикет #{t.id} создан. Поддержка ответит здесь/через Telegram.')

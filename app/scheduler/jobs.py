from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from app.db.session import Session
from app.db.models import Subscription,User,NotificationLog
from app.config import settings
from app.services.remnawave import RemnawaveClient
async def run_expiration(bot):
    now=datetime.now(timezone.utc)
    async with Session() as s:
        active=(await s.execute(select(Subscription,User).join(User,Subscription.user_id==User.id).where(Subscription.active==True))).all()
        for sub,u in active:
            sec=(sub.expires_at-now).total_seconds();targets=sorted([d for d in settings.reminder_day_set if d>0],reverse=True);target=next((d for d in targets if sec<=d*86400),None)
            if sec<=0: target=0
            if target is None: continue
            if not await s.scalar(select(NotificationLog.id).where(NotificationLog.subscription_id==sub.id,NotificationLog.reminder_day==target)):
                if target==0:
                    sub.active=False
                    if settings.grace_enabled and settings.grace_squad_uuid and sub.remnawave_user_uuid:
                        try:
                            sub.grace_until=now+timedelta(hours=settings.grace_hours);await RemnawaveClient().update_user(sub.remnawave_user_uuid,sub.grace_until,[settings.grace_squad_uuid])
                        except Exception: pass
                    text='❌ Подписка закончилась. Нажмите «Продлить» в боте. Ограниченный режим может быть доступен по настройкам сервиса.'
                else: text=f'⚠️ До окончания подписки осталось примерно {target} дн. Продлить можно уже сейчас.'
                try: await bot.send_message(u.telegram_id,text)
                except Exception: pass
                s.add(NotificationLog(subscription_id=sub.id,reminder_day=target))
        expired_grace=(await s.execute(select(Subscription).where(Subscription.grace_until.is_not(None),Subscription.grace_until<=now))).scalars().all()
        for sub in expired_grace:
            if sub.remnawave_user_uuid:
                try: await RemnawaveClient().disable(sub.remnawave_user_uuid)
                except Exception: pass
            sub.grace_until=None
        await s.commit()

from datetime import datetime,timezone,timedelta
from decimal import Decimal
from aiogram import Router,F
from aiogram.types import CallbackQuery,Message
from aiogram.fsm.state import State,StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select,func,or_
from app.config import settings
from app.db.session import Session
from app.db.models import User,Plan,PlanPeriod,Payment,PromoCode,Subscription,Partner,AdminLog,Broadcast,Ticket,TicketMessage
from app.bot.keyboards import admin as admin_kb,user_actions,K
from app.services.remnawave import RemnawaveClient
router=Router()
def is_admin(uid): return uid in settings.admin_id_set
class AState(StatesGroup): input=State()
@router.callback_query(F.data=='admin')
async def adm(c):
    if is_admin(c.from_user.id): await c.message.answer('⚙️ <b>Админ-панель</b>',reply_markup=admin_kb());await c.answer()
@router.callback_query(F.data=='ausers')
async def ausers(c):
    if not is_admin(c.from_user.id): return
    async with Session() as s: us=(await s.execute(select(User).order_by(User.id.desc()).limit(30))).scalars().all()
    await c.message.answer('👥 Последние пользователи:\n\n'+'\n'.join([f'#{u.id} @{u.username or "-"} — {u.telegram_id}' for u in us])+'\n\nОткрыть: /user ID');await c.answer()
@router.message(F.text.regexp(r'^/find\s+.+$'))
async def find_user(m):
    if not is_admin(m.from_user.id): return
    q=m.text.split(maxsplit=1)[1].strip().lstrip('@')
    async with Session() as s:
        us=(await s.execute(select(User).where(or_(User.username.ilike(f"%{q}%"),User.first_name.ilike(f"%{q}%"),User.telegram_id.cast(str).like(f"%{q}%"))).order_by(User.id.desc()).limit(20))).scalars().all()
    await m.answer('🔎 Результаты:\n'+('\n'.join([f'#{{u.id}} @{{u.username or "-"}} — {{u.telegram_id}}' for u in us]) if us else 'ничего не найдено'))
@router.message(F.text.regexp(r'^/user\s+\d+$'))
async def user_cmd(m):
    if is_admin(m.from_user.id): await show_user(m,int(m.text.split()[1]))
async def show_user(target,uid):
    async with Session() as s:
        u=(await s.execute(select(User).where(User.id==uid))).scalar_one_or_none();sub=(await s.execute(select(Subscription).where(Subscription.user_id==uid,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first()
    if not u: await target.answer('Не найден');return
    txt=f'👤 <b>{u.first_name or "Пользователь"}</b>\nTG ID: {u.telegram_id}\nUsername: @{u.username or "-"}\nПерсональная скидка: {u.personal_discount}%\nTrial: {u.trial_used}\nЗаблокирован: {u.blocked}\n'
    if sub: txt+=f'Подписка до: {sub.expires_at.astimezone().strftime("%d.%m.%Y %H:%M")}\nPlan: {sub.plan_id}\nRW UUID: {sub.remnawave_user_uuid or "-"}'
    await target.answer(txt,reply_markup=user_actions(uid))
@router.callback_query(F.data.startswith('uext:'))
async def uext(c):
    if not is_admin(c.from_user.id): return
    _,uid,days=c.data.split(':');uid=int(uid);days=int(days)
    async with Session() as s:
        sub=(await s.execute(select(Subscription).where(Subscription.user_id==uid,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first()
        if sub: sub.expires_at=max(sub.expires_at,datetime.now(timezone.utc))+timedelta(days=days);await s.commit();rwuid=sub.remnawave_user_uuid;end=sub.expires_at;squads=sub.squad_uuids
    if rwuid:
        try: await RemnawaveClient().update_user(rwuid,end,squads)
        except: pass
    await c.message.answer('✅ Срок продлён.')
@router.callback_query(F.data.startswith('uadj:'))
async def uadj(c):
    if not is_admin(c.from_user.id): return
    _,uid,days=c.data.split(':');uid=int(uid);days=int(days)
    async with Session() as s:
        sub=(await s.execute(select(Subscription).where(Subscription.user_id==uid,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first()
        if sub: sub.expires_at+=timedelta(days=days);await s.commit()
    await c.message.answer('✅ Срок изменён.')
@router.callback_query(F.data.startswith('udisc:'))
async def udisc(c,state):
    if not is_admin(c.from_user.id): return
    await state.update_data(target_user=int(c.data.split(':')[1]));await state.set_state(AState.input);await c.message.answer('Введите персональную скидку 0-100:');await c.answer()
@router.callback_query(F.data.startswith('ugrant:'))
async def ugrant(c,state):
    if not is_admin(c.from_user.id): return
    await state.update_data(grant_user=int(c.data.split(':')[1]));await state.set_state(AState.input);await c.message.answer('Введите: дни | plan_id\nНапример: 30 | 2')
@router.callback_query(F.data.startswith('ublock:'))
async def ublock(c):
    if not is_admin(c.from_user.id): return
    uid=int(c.data.split(':')[1])
    async with Session() as s:
        u=(await s.execute(select(User).where(User.id==uid))).scalar_one();u.blocked=not u.blocked;blocked=u.blocked;rwuid=(await s.execute(select(Subscription.remnawave_user_uuid).where(Subscription.user_id==uid).order_by(Subscription.expires_at.desc()))).scalar_one_or_none();await s.commit();state=blocked
    if rwuid:
        try:
            rw=RemnawaveClient(); await (rw.disable(rwuid) if state else rw.enable(rwuid))
        except Exception: pass
    await c.message.answer('🚫 Заблокирован' if state else '✅ Разблокирован')
@router.callback_query(F.data.startswith('ursync:'))
async def ursync(c):
    if not is_admin(c.from_user.id): return
    uid=int(c.data.split(':')[1])
    async with Session() as s:
        u=(await s.execute(select(User).where(User.id==uid))).scalar_one()
    try:
        rw=RemnawaveClient();ru=await rw.find_user_by_telegram_id(u.telegram_id);await c.message.answer(f'✅ Remnawave: {ru}')
    except Exception as e: await c.message.answer(f'❌ {e}')
@router.message(AState.input)
async def state_input(m,state):
    if not is_admin(m.from_user.id): return
    d=await state.get_data();txt=m.text.strip()
    if 'target_user' in d:
        try:v=max(0,min(100,int(txt)))
        except: await m.answer('Введите число 0-100');return
        async with Session() as s:u=(await s.execute(select(User).where(User.id==d['target_user']))).scalar_one();u.personal_discount=v;await s.commit()
        await state.clear();await m.answer('✅ Скидка сохранена.');return
    if 'grant_user' in d:
        try:days,planid=[x.strip() for x in txt.split('|',1)];days=int(days);planid=int(planid)
        except: await m.answer('Формат: дни | plan_id');return
        async with Session() as s:
            u=(await s.execute(select(User).where(User.id==d['grant_user']))).scalar_one();p=(await s.execute(select(Plan).where(Plan.id==planid))).scalar_one();now=datetime.now(timezone.utc);old=(await s.execute(select(Subscription).where(Subscription.user_id==u.id,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first();start=old.expires_at if old and old.expires_at>now else now;end=start+timedelta(days=days);squads=p.squad_uuids
            rw=RemnawaveClient();ru=await rw.find_user_by_telegram_id(u.telegram_id);uuid=ru.get('uuid') if isinstance(ru,dict) else None
            if uuid: await rw.update_user(uuid,end,squads,p.device_limit,p.traffic_limit_gb)
            else: ru=await rw.create_user(f'tg_{u.telegram_id}',end,u.telegram_id,squads,p.device_limit,p.traffic_limit_gb);uuid=ru.get('uuid')
            if old: old.expires_at=end;old.plan_id=p.id;old.remnawave_user_uuid=uuid
            else:s.add(Subscription(user_id=u.id,plan_id=p.id,started_at=start,expires_at=end,remnawave_user_uuid=uuid,squad_uuids=squads,device_limit=p.device_limit,traffic_limit_gb=p.traffic_limit_gb))
            await s.commit()
        await state.clear();await m.answer('✅ Подписка выдана.');return
    if d.get('newplan'):
        try:name,desc,price,squads,device,traffic=[x.strip() for x in txt.split('|',5)];price=Decimal(price);device=int(device);traffic=int(traffic);sq=[x for x in squads.split(',') if x]
        except: await m.answer('Формат: name | desc | 30d_price | squads_csv | devices | traffic_gb');return
        async with Session() as s:p=Plan(name=name,description=desc,squad_uuids=sq,device_limit=device,traffic_limit_gb=traffic);s.add(p);await s.flush();s.add(PlanPeriod(plan_id=p.id,days=30,price=price));await s.commit()
        await state.clear();await m.answer('✅ Тариф создан.');return
    if d.get('editplan'):
        try:name,desc,squads,device,traffic=[x.strip() for x in txt.split('|',4)];device=int(device);traffic=int(traffic);sq=[x for x in squads.split(',') if x]
        except: await m.answer('Формат: name | desc | squads_csv | devices | traffic_gb');return
        async with Session() as s:
            p=(await s.execute(select(Plan).where(Plan.id==d['editplan']))).scalar_one();p.name=name;p.description=desc;p.squad_uuids=sq;p.device_limit=device;p.traffic_limit_gb=traffic;await s.commit()
        await state.clear();await m.answer('✅ Тариф обновлён.');return
    if d.get('newperiod'):
        try:planid,days,price=[x.strip() for x in txt.split('|',2)];planid=int(planid);days=int(days);price=Decimal(price)
        except: await m.answer('Формат: plan_id | days | price');return
        async with Session() as s:s.add(PlanPeriod(plan_id=planid,days=days,price=price));await s.commit()
        await state.clear();await m.answer('✅ Период добавлен.');return
    if d.get('newpromo'):
        try:code,kind,value,maxuses,planid=[x.strip() for x in txt.split('|',4)];value=Decimal(value);maxuses=int(maxuses);planid=int(planid)
        except: await m.answer('Формат: CODE | PERCENT/FIXED/FREE | value | max_uses | plan_id(0)');return
        async with Session() as s:s.add(PromoCode(code=code.upper(),kind=kind.upper(),value=value,max_uses=maxuses,target_plan_id=planid or None));await s.commit()
        await state.clear();await m.answer('✅ Промокод создан.');return
    if d.get('newpartner'):
        try:name,code,comm=[x.strip() for x in txt.split('|',2)];comm=Decimal(comm)
        except: await m.answer('Формат: имя | code | commission');return
        async with Session() as s:s.add(Partner(name=name,code=code,commission_percent=comm));await s.commit()
        await state.clear();await m.answer('✅ Партнёр создан.');return
    if d.get('broadcast_audience'):
        aud=d['broadcast_audience'];
        async with Session() as s:
            users=(await s.execute(select(User))).scalars().all();sent=failed=0
            for u in users:
                ok=False
                if u.blocked: continue
                if aud=='all': ok=True
                elif aud=='active': ok=bool(await s.scalar(select(Subscription.id).where(Subscription.user_id==u.id,Subscription.active==True)))
                elif aud=='expired': ok=not bool(await s.scalar(select(Subscription.id).where(Subscription.user_id==u.id,Subscription.active==True)))
                elif aud=='trial': ok=u.trial_used
                elif aud=='buyers': ok=bool(await s.scalar(select(Payment.id).where(Payment.user_id==u.id,Payment.status=='COMPLETED')))
                if ok:
                    try: await m.bot.send_message(u.telegram_id,txt);sent+=1
                    except: failed+=1
            s.add(Broadcast(audience=aud,text=txt,sent=sent,failed=failed));await s.commit()
        await state.clear();await m.answer(f'✅ Рассылка: {sent} отправлено, {failed} ошибок.');return

@router.message(F.text.regexp(r'^/partnerstats\s+\S+$'))
async def partnerstats(m):
    if not is_admin(m.from_user.id): return
    code=m.text.split()[1]
    async with Session() as s:
        p=(await s.execute(select(Partner).where(Partner.code==code))).scalar_one_or_none()
    if not p: await m.answer('Партнёр не найден');return
    await m.answer(f'🤝 {p.name}\nКод: {p.code}\nСсылка: t.me/{(await m.bot.get_me()).username}?start=partner_{p.code}\nПереходов: {p.clicks}\nРегистраций: {p.registrations}\nПокупок: {p.purchases}\nКомиссия: {p.commission_percent}%\nБаланс: {p.payout_balance} ₽')
@router.message(F.text.regexp(r'^/msg\s+\d+\s+.+'))
async def directmsg(m):
    if not is_admin(m.from_user.id): return
    _,tid,*rest=m.text.split();text=' '.join(rest)
    try: await m.bot.send_message(int(tid),text);await m.answer('✅ Сообщение отправлено.')
    except Exception as e: await m.answer(f'❌ Не отправлено: {e}')
@router.callback_query(F.data=='aplans')
async def aplans(c):
    if not is_admin(c.from_user.id): return
    async with Session() as s: ps=(await s.execute(select(Plan).order_by(Plan.id))).scalars().all()
    await c.message.answer('📦 Тарифы:\n'+'\n'.join([f'{p.id}. {p.name} — {"🟢" if p.active else "🔴"}' for p in ps])+'\n\n/newplan — создать\n/addperiod — добавить срок');await c.answer()
@router.message(F.text=='/newplan')
async def newplan(m,state):
    if is_admin(m.from_user.id): await state.update_data(newplan=True);await state.set_state(AState.input);await m.answer('name | desc | 30d_price | squad1,squad2 | devices | traffic_gb')
@router.message(F.text.regexp(r'^/editplan\s+\d+$'))
async def editplan(m,state):
    if is_admin(m.from_user.id):
        await state.update_data(editplan=int(m.text.split()[1]));await state.set_state(AState.input);await m.answer('name | desc | squads_csv | devices | traffic_gb')
@router.message(F.text.regexp(r'^/toggleplan\s+\d+$'))
async def toggleplan(m):
    if not is_admin(m.from_user.id): return
    pid=int(m.text.split()[1])
    async with Session() as s:
        p=(await s.execute(select(Plan).where(Plan.id==pid))).scalar_one_or_none()
        if not p: await m.answer('План не найден');return
        p.active=not p.active;await s.commit();await m.answer(f'✅ {p.name}: {p.active}')
@router.message(F.text=='/addperiod')
async def addperiod(m,state):
    if is_admin(m.from_user.id): await state.update_data(newperiod=True);await state.set_state(AState.input);await m.answer('plan_id | days | price')
@router.callback_query(F.data=='apromo')
async def apromo(c):
    if is_admin(c.from_user.id): await c.message.answer('🎁 /newpromo\nCODE | PERCENT/FIXED/FREE | value | max_uses | plan_id');await c.answer()
@router.message(F.text=='/newpromo')
async def newpromo(m,state):
    if is_admin(m.from_user.id): await state.update_data(newpromo=True);await state.set_state(AState.input);await m.answer('CODE | PERCENT/FIXED/FREE | value | max_uses | plan_id(0)')
@router.callback_query(F.data=='apartners')
async def apartners(c):
    if is_admin(c.from_user.id): await c.message.answer('🤝 /newpartner\nимя | code | commission\n\nСсылка партнёра: /start partner_CODE');await c.answer()
@router.message(F.text=='/newpartner')
async def newpartner(m,state):
    if is_admin(m.from_user.id): await state.update_data(newpartner=True);await state.set_state(AState.input);await m.answer('имя | code | commission')
@router.callback_query(F.data=='abroadcast')
async def abroadcast(c):
    if not is_admin(c.from_user.id): return
    await c.message.answer('Выберите аудиторию:',reply_markup=K([[('👥 Все','bca:all'),('🟢 Активные','bca:active')],[('🔴 Истёкшие','bca:expired'),('💳 Покупатели','bca:buyers')],[('🧪 Trial','bca:trial')]]));await c.answer()
@router.callback_query(F.data.startswith('bca:'))
async def bca(c,state):
    if not is_admin(c.from_user.id): return
    aud=c.data.split(':')[1];await state.update_data(broadcast_audience=aud);await state.set_state(AState.input);await c.message.answer('Введите текст рассылки:');await c.answer()
@router.callback_query(F.data=='astats')
async def stats(c):
    async with Session() as s:
        users=await s.scalar(select(func.count(User.id)));active=await s.scalar(select(func.count(Subscription.id)).where(Subscription.active==True));paid=await s.scalar(select(func.count(Payment.id)).where(Payment.status=='COMPLETED'));rev=await s.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.status=='COMPLETED'));tickets=await s.scalar(select(func.count(Ticket.id)).where(Ticket.status=='OPEN'))
    await c.message.answer(f'📊 Пользователи: {users}\n🟢 Активные: {active}\n💳 Покупки: {paid}\n💰 Выручка: {rev} ₽\n🆘 Открытые тикеты: {tickets}');await c.answer()
@router.callback_query(F.data=='apay')
async def paylist(c):
    if not is_admin(c.from_user.id): return
    async with Session() as s: ps=(await s.execute(select(Payment).order_by(Payment.id.desc()).limit(20))).scalars().all()
    await c.message.answer('💳 Последние платежи:\n'+'\n'.join([f'#{p.id} {p.amount} ₽ — {p.status}' for p in ps]));await c.answer()
@router.callback_query(F.data=='aservers')
async def servers(c):
    if not is_admin(c.from_user.id): return
    try:
        rw=RemnawaveClient();nodes=await rw.list_nodes();lines=[f'{n.get("name","-")} — {n.get("status",n.get("isOnline","?"))}' for n in nodes or []];stats=await rw.req('GET','/system/nodes-statistics');await c.message.answer('🖥 <b>Ноды</b>\n'+'\n'.join(lines)+'\n\n📈 Stats:\n'+str(stats)[:3000])
    except Exception as e: await c.message.answer(f'❌ Remnawave: {e}')
    await c.answer()
@router.callback_query(F.data.in_({'atrial','agrace','anotify','asettings'}))
async def settings_view(c):
    if not is_admin(c.from_user.id): return
    await c.message.answer(f'⚙️ Настройки сейчас задаются Environment Variables.\n\nTRIAL_ENABLED={settings.trial_enabled}\nTRIAL_DAYS={settings.trial_days}\nGRACE_ENABLED={settings.grace_enabled}\nGRACE_HOURS={settings.grace_hours}\nREMINDER_DAYS={settings.reminder_days}\nREFERRAL_REWARD_DAYS={settings.referral_reward_days}\n\nИзменить для теста: /settrial true|3\n/setgrace true|24\n/setreminders 7,3,1,0');await c.answer()
@router.message(F.text.startswith('/settrial'))
async def settrial(m):
    if not is_admin(m.from_user.id): return
    try: enabled,days=m.text.split()[1].split('|');settings.trial_enabled=enabled.lower()=='true';settings.trial_days=int(days);await m.answer('✅ Только на текущем процессе. Для постоянного значения используй Render/VPS env.')
    except: await m.answer('Формат: /settrial true|3')
@router.message(F.text.startswith('/setgrace'))
async def setgrace(m):
    if not is_admin(m.from_user.id): return
    try: enabled,h=m.text.split()[1].split('|');settings.grace_enabled=enabled.lower()=='true';settings.grace_hours=int(h);await m.answer('✅ Настройка применена текущему процессу.')
    except: await m.answer('Формат: /setgrace true|24')
@router.message(F.text.startswith('/setreminders'))
async def setrem(m):
    if not is_admin(m.from_user.id): return
    settings.reminder_days=m.text.split(maxsplit=1)[1];await m.answer('✅ Напоминания обновлены для текущего процесса.')
@router.message(F.text.startswith('/setref'))
async def setref(m):
    if not is_admin(m.from_user.id): return
    try: days,require=m.text.split()[1].split('|');settings.referral_reward_days=int(days);settings.referral_require_purchase=require.lower()=='purchase';await m.answer('✅ Реферальные настройки применены к текущему процессу.')
    except: await m.answer('Формат: /setref 7|purchase')
@router.message(F.text.regexp(r'^/reply\s+\d+\s+.+'))
async def reply_ticket(m):
    if not is_admin(m.from_user.id): return
    _,tid,*rest=m.text.split();text=' '.join(rest);tid=int(tid)
    async with Session() as s:
        t=(await s.execute(select(Ticket).where(Ticket.id==tid,Ticket.status=='OPEN'))).scalar_one_or_none()
        if not t: await m.answer('Тикет не найден');return
        u=(await s.execute(select(User).where(User.id==t.user_id))).scalar_one();s.add(TicketMessage(ticket_id=t.id,author_telegram_id=m.from_user.id,text=text));await s.commit()
    await m.bot.send_message(u.telegram_id,f'💬 Ответ поддержки по тикету #{tid}:\n\n{text}');await m.answer('✅ Ответ отправлен.')

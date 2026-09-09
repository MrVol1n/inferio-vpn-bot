from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from app.db.models import User,Plan,PlanPeriod,Payment,PromoCode,PromoUsage,Subscription,Referral,Partner,PartnerConversion
from app.services.remnawave import RemnawaveClient
async def calc_price(s,user,plan,period,promo_code=None):
    price=Decimal(str(period.price)); discount=int(user.personal_discount or 0); promo=None
    if promo_code:
        promo=(await s.execute(select(PromoCode).where(PromoCode.code==promo_code.upper(),PromoCode.active==True))).scalar_one_or_none()
        if promo and (promo.target_plan_id is None or promo.target_plan_id==plan.id) and (promo.max_uses==0 or promo.used_count<promo.max_uses):
            used=await s.scalar(select(PromoUsage).where(PromoUsage.promo_id==promo.id,PromoUsage.user_id==user.id))
            if not used:
                if promo.kind=='PERCENT': discount=min(100,discount+int(promo.value))
                elif promo.kind=='FIXED': price=max(Decimal('0'),price-Decimal(promo.value))
                elif promo.kind=='FREE': price=Decimal('0')
                elif promo.kind=='BONUS_DAYS': pass
    if discount: price=(price*(Decimal(100-discount)/100)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    return price,promo
async def provision_payment(s,payment_id,bot):
    p=(await s.execute(select(Payment).where(Payment.id==payment_id))).scalar_one()
    if p.status=='COMPLETED': return
    user=(await s.execute(select(User).where(User.id==p.user_id))).scalar_one()
    plan=(await s.execute(select(Plan).where(Plan.id==p.plan_id))).scalar_one(); period=(await s.execute(select(PlanPeriod).where(PlanPeriod.id==p.period_id))).scalar_one()
    now=datetime.now(timezone.utc)
    old=(await s.execute(select(Subscription).where(Subscription.user_id==user.id,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first()
    start=old.expires_at if old and old.expires_at>now else now; end=start+timedelta(days=period.days)
    rw=RemnawaveClient(); rw_user=None
    try: rw_user=await rw.find_user_by_telegram_id(user.telegram_id)
    except Exception: rw_user=None
    uuid=(rw_user or {}).get('uuid') if isinstance(rw_user,dict) else None
    if uuid: await rw.update_user(uuid,end,plan.squad_uuids,plan.device_limit,plan.traffic_limit_gb)
    else:
        created=await rw.create_user(f'tg_{user.telegram_id}',end,user.telegram_id,plan.squad_uuids,plan.device_limit,plan.traffic_limit_gb); uuid=created.get('uuid') or created.get('UUID')
    url=None
    try:
        sub=await rw.get_subscription_by_uuid(uuid); url=sub.get('subscriptionUrl') if isinstance(sub,dict) else None
    except Exception: pass
    if old:
        old.plan_id=plan.id; old.expires_at=end; old.remnawave_user_uuid=uuid; old.squad_uuids=plan.squad_uuids; old.device_limit=plan.device_limit; old.traffic_limit_gb=plan.traffic_limit_gb; old.subscription_url=url or old.subscription_url
        subdb=old
    else:
        subdb=Subscription(user_id=user.id,plan_id=plan.id,started_at=start,expires_at=end,remnawave_user_uuid=uuid,squad_uuids=plan.squad_uuids,device_limit=plan.device_limit,traffic_limit_gb=plan.traffic_limit_gb,subscription_url=url); s.add(subdb)
    p.status='COMPLETED'; p.confirmed_at=now
    bonus_days=0
    if p.promo_code:
        pp=(await s.execute(select(PromoCode).where(PromoCode.code==p.promo_code))).scalar_one_or_none()
        if pp and pp.kind=='BONUS_DAYS': bonus_days=int(pp.value)
    if bonus_days:
        end += timedelta(days=bonus_days); subdb_expires=end
    if bonus_days:
        subdb.expires_at=end
        try: await rw.update_user(uuid,end,plan.squad_uuids,plan.device_limit,plan.traffic_limit_gb)
        except Exception: pass
    if p.promo_code:
        promo=(await s.execute(select(PromoCode).where(PromoCode.code==p.promo_code))).scalar_one_or_none()
        if promo: promo.used_count+=1; s.add(PromoUsage(promo_id=promo.id,user_id=user.id,payment_id=p.id))
    ref=(await s.execute(select(Referral).where(Referral.invited_id==user.id,Referral.rewarded==False))).scalar_one_or_none()
    if ref:
        rs=(await s.execute(select(Subscription).where(Subscription.user_id==ref.referrer_id,Subscription.active==True).order_by(Subscription.expires_at.desc()))).scalars().first()
        if rs:
            rs.expires_at += timedelta(days=__import__('app.config',fromlist=['settings']).settings.referral_reward_days)
            try: await rw.update_user(rs.remnawave_user_uuid,rs.expires_at,rs.squad_uuids,rs.device_limit,rs.traffic_limit_gb)
            except Exception: pass
            try: await bot.send_message((await s.execute(select(User.telegram_id).where(User.id==ref.referrer_id))).scalar_one(),'🎁 Реферальный бонус: +7 дней.')
            except Exception: pass
        ref.rewarded=True
    if user.partner_id:
        partner=(await s.execute(select(Partner).where(Partner.id==user.partner_id,Partner.active==True))).scalar_one_or_none()
        if partner:
            commission=(Decimal(p.amount)*Decimal(partner.commission_percent)/100).quantize(Decimal('0.01')); partner.payout_balance+=commission; partner.purchases+=1; s.add(PartnerConversion(partner_id=partner.id,user_id=user.id,payment_id=p.id,amount=p.amount,commission=commission))
    await s.commit(); return subdb

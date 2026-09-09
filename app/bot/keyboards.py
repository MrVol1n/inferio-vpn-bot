from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
def K(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data=d) if not d.startswith('https://') else InlineKeyboardButton(text=t,url=d) for t,d in row] for row in rows])
def main(admin=False):
    r=[[('🛒 Купить VPN','buy'),('👤 Моя подписка','me')],[('🎁 Trial','trial'),('🔗 Подключение','connect')],[('🎁 Промокод','promo'),('👥 Рефералы','ref')],[('💬 Поддержка','support')],[('📜 Соглашение','terms'),('🔒 Политика','privacy')]]
    if admin:r.append([('⚙️ Админ-панель','admin')])
    return K(r)
def back(cb='home'): return K([[('⬅️ Назад',cb)]])
def plans(ps): return K([[(p.name,f'plan:{p.id}')] for p in ps]+[[('⬅️ Назад','home')]])
def periods(p,items): return K([[(f'{x.days} дней — {x.price} ₽',f'period:{p.id}:{x.id}')] for x in items]+[[('⬅️ Назад','buy')]])
def pay(url,pid): return K([[('💳 Оплатить',url)],[('🔄 Проверить оплату',f'checkpay:{pid}')],[('⬅️ К покупкам','buy')]])
def admin(): return K([[('👥 Пользователи','ausers'),('📦 Тарифы','aplans')],[('💳 Платежи','apay'),('🎁 Промокоды','apromo')],[('🧪 Trial','atrial'),('🎁 Grace','agrace')],[('👥 Рефералы','aref'),('🤝 Партнёры','apartners')],[('📢 Рассылки','abroadcast'),('🖥 Серверы','aservers')],[('📊 Статистика','astats'),('⚙️ Настройки','asettings')],[('🏠 Главное','home')]])
def user_actions(uid): return K([[('➕30 дней',f'uext:{uid}:30'),('➕90 дней',f'uext:{uid}:90')],[('➖7 дней',f'uadj:{uid}:-7'),('💸 Скидка',f'udisc:{uid}')],[('🎁 Выдать',f'ugrant:{uid}'),('🚫 Блок/разблок',f'ublock:{uid}')],[('🔄 Remnawave',f'ursync:{uid}')],[('⬅️ Пользователи','ausers')]])

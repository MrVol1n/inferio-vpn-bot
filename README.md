# INFERIO VPN — final test build

Проект рассчитан на два окружения:
- **Render** для первого теста: Web Service + Background Worker + PostgreSQL.
- **Ubuntu VPS** для дальнейшей работы: Docker Compose.

Картинка из запроса уже лежит в `assets/welcome.jpg` и используется на главном экране.

## Что реализовано

Клиент:
- обязательное принятие пользовательского соглашения и политики;
- главное меню с картинкой;
- тарифы и несколько сроков;
- оплата через Platega;
- callback Platega + ручная проверка статуса;
- автоматическая выдача/продление пользователя в Remnawave;
- Squads на тарифах;
- личный кабинет;
- subscription URL и инструкции подключения;
- trial;
- промокоды: процент, фиксированная скидка, бесплатная подписка, бонусные дни;
- персональная скидка;
- реферальная система;
- партнёрские ссылки и статистика;
- поддержка через тикеты;
- автоматические уведомления об окончании;
- Grace Access через отдельный Squad.

Админ:
- пользователи;
- ручное продление/уменьшение;
- выдача подписки;
- персональная скидка;
- блокировка + синхронизация с Remnawave;
- тарифы, создание, редактирование, включение/выключение;
- дополнительные сроки тарифов;
- промокоды;
- партнёры;
- рассылка по аудиториям: все, активные, истёкшие, покупатели, trial;
- статистика;
- список Remnawave Nodes + системная статистика;
- настройка trial/grace/напоминаний/реферальной награды через env/команды тестового процесса;
- прямое сообщение пользователю `/msg TG_ID текст`;
- ответы поддержки `/reply TICKET_ID текст`.

## Важно про Remnawave

Интеграция построена вокруг актуальных REST API маршрутов Remnawave: `/api/users`, `/api/users/by-telegram-id/{telegramId}`, `/api/users/{uuid}/actions/enable`, `/disable`, `/revoke`, `/api/internal-squads`, `/api/nodes`, `/api/system/nodes-statistics`, `/api/subscriptions/by-uuid/{uuid}`. Перед боевым запуском проверь, что твоя версия панели и выданный API token имеют эти scope/маршруты.

## 1. Тест на Render

1. Создай **private GitHub repository** и залей содержимое папки проекта.
2. Render → **New → Blueprint** → выбери репозиторий → Deploy Blueprint.
3. Будут созданы:
   - `inferio-vpn-web` — публичный HTTPS endpoint;
   - `inferio-vpn-worker` — Telegram polling + планировщик;
   - `inferio-db` — PostgreSQL.
4. В Environment Variables заполни:

```text
BOT_TOKEN=токен от @BotFather
ADMIN_IDS=твой_числовой_Telegram_ID
PUBLIC_BASE_URL=https://inferio-vpn-web.onrender.com
SUPPORT_USERNAME=@твой_support
TERMS_TEXT=текст соглашения
PRIVACY_TEXT=текст политики
PLATEGA_MERCHANT_ID=MerchantId
PLATEGA_SECRET=Secret
PLATEGA_RETURN_URL=https://inferio-vpn-web.onrender.com/payment/return
PLATEGA_CALLBACK_URL=https://inferio-vpn-web.onrender.com/webhooks/platega
REMNAWAVE_BASE_URL=https://panel.example.com
REMNAWAVE_TOKEN=API token Remnawave
TRIAL_SQUAD_UUIDS=uuid-trial
GRACE_SQUAD_UUID=uuid-grace
```

5. Проверь:

```text
https://inferio-vpn-web.onrender.com/health
```

6. В Platega → Callback URLs укажи:

```text
https://inferio-vpn-web.onrender.com/webhooks/platega
```

Platega требует публичный HTTPS endpoint для callback и отправляет `X-MerchantId`, `X-Secret` и JSON со статусом `CONFIRMED`, `CANCELED` или `CHARGEBACKED`.

## 2. Что получить в Remnawave

В панели Remnawave создай API token и проверь доступ к Users/Nodes/Internal Squads.

Сделай, например:

```text
Default Squad
Bypass Squad
Grace Squad
Trial Squad
```

UUID этих Squad вставляй в тарифы/Environment Variables.

Текущая документация Remnawave подтверждает, что пользователь получает `Subscription URL`, а Internal Squads определяют доступ пользователя; пользователя можно добавить сразу в несколько Internal Squads.

## 3. Админские команды

```text
/user ID                    открыть пользователя
/find QUERY                  поиск по Telegram ID/username (можно добавить при необходимости)
/newplan                     создать тариф
/editplan ID                 изменить тариф
/toggleplan ID               включить/выключить тариф
/addperiod                   добавить срок тарифу
/newpromo                    создать промокод
/newpartner                  создать партнёра
/partnerstats CODE           статистика партнёра
/msg TG_ID текст             личное сообщение
/reply TICKET_ID текст       ответ на тикет
/settrial true|3             включить trial на 3 дня для текущего процесса
/setgrace true|24            grace на 24 часа для текущего процесса
/setreminders 7,3,1,0        напоминания
/setref 7|purchase           реферальный бонус +7 дней после покупки
```

Форматы:

```text
/newplan
name | desc | 30d_price | squad1,squad2 | devices | traffic_gb

/editplan ID
name | desc | squad1,squad2 | devices | traffic_gb

/addperiod
plan_id | days | price

/newpromo
CODE | PERCENT/FIXED/FREE/BONUS_DAYS | value | max_uses | plan_id(0)

/newpartner
имя | code | commission
```

`FREE` с `plan_id` выдаёт выбранный тариф бесплатно. `BONUS_DAYS` добавляет бонусные дни после подтверждённой оплаты.

## 4. Ubuntu VPS позже

На VPS нужен только Docker + Git.

Клонирование:

```bash
sudo mkdir -p /opt
cd /opt
git clone https://github.com/ТВОЙ_GITHUB/ТВОЙ_REPO.git inferio
cd /opt/inferio
```

Если репозиторий уже клонирован:

```bash
cd /opt/inferio
git pull
```

Создай env:

```bash
cp .env.example .env
nano .env
```

Запуск:

```bash
docker compose up -d --build
```

Проверка:

```bash
docker compose ps
docker compose logs -f worker
```

Web health:

```text
http://SERVER_IP:10000/health
```

Для callback Platega на VPS нужен домен + HTTPS через reverse proxy.

## 5. Что менять тебе

Главное — только Environment Variables. Не нужно вставлять секреты в Python-код.

```text
BOT_TOKEN
ADMIN_IDS
PLATEGA_MERCHANT_ID
PLATEGA_SECRET
REMNAWAVE_BASE_URL
REMNAWAVE_TOKEN
SUPPORT_USERNAME
TERMS_TEXT
PRIVACY_TEXT
```

Тарифы, сроки, Squads и промокоды в дальнейшем меняются через админку/команды.

**Не добавляй `.env` в GitHub.** Он уже указан в `.gitignore`.

# Market Place API (DRF)

API-only маркетплейс косметики: розница + опт, платежи Stripe, комиссии платформы, кошельки продавцов.

## Стек

- Python 3.12, Django 6, DRF 3.18, SimpleJWT, drf-yasg (Swagger/ReDoc)
- Channels + WebSocket (уведомления, чат), Celery (email-дубли)
- SQLite (dev) / PostgreSQL, Redis (кэш + channel layer), Stripe (платежи), Pillow

## Быстрый старт

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_data      # демо: admin/buyer/seller, магазин, категории, 14 товаров
python manage.py runserver
```

- Swagger UI: http://127.0.0.1:8000/swagger/
- ReDoc: http://127.0.0.1:8000/redoc/

### Docker (Postgres + Redis + nginx + API + Celery worker)

```bash
docker compose up --build -d
```

Два входа (для деплоя откройте на сервере порты 80 и 8000):

| Вход | Адрес | Что это |
|------|-------|---------|
| **Основной** | `http://<ip>/` | через nginx: статика, медиа, WebSocket, API |
| Прямой | `http://<ip>:8000/` | daphne напрямую, без статики |

- Swagger UI: `http://<ip>/swagger/`
- ReDoc: `http://<ip>/redoc/`
- Структура прокси: `nginx/nginx.conf` (`/static/`, `/media/`, `/ws/` → daphne)

### Демо-доступы (пароли из seed_data)

| Роль | Логин | Пароль |
|------|-------|--------|
| Админ | admin@beauty.ru | Admin123! |
| Покупатель | buyer@beauty.ru | Buyer123! |
| Продавец | seller@beauty.ru | Seller123! |

## Тесты

```bash
python manage.py test
```

Покрыты: авторизация, каталог (фильтры/поиск/отзывы/избранное), корзина → заказ → оплата → комиссия → кошелёк → выплата, возвраты, уведомления, магазины, чат (заказ/товар/магазин + вложения), техподдержка.

## WebSocket

| Канал | Назначение |
|-------|-----------|
| `/ws/notifications/?token=<access>` | личные уведомления |
| `/ws/chat/<thread_id>/?token=<access>` | сообщения диалога |

Токен — access JWT. Вложения в чате/тикетах отправляются по REST (`multipart`), WS — только текст.

## Основные API

| Область | Эндпоинты |
|---------|-----------|
| Auth | `/api/auth/register/buyer/`, `register/seller/`, `login/`, `refresh/` |
| Каталог | `/api/feed/`, `/categories/`, `/products/`, `/brands/`, `/search/suggest/` |
| Корзина/заказ | `/api/cart/`, `/api/checkout/`, `/api/orders/` |
| Платежи | `/api/payments/<order>/create/`, `webhook/stripe/` |
| Продавец | `/api/seller/dashboard/`, `products/`, `orders/`, `stock/` |
| Финансы | `/api/finance/wallet/`, `payouts/` |
| Чат | `/api/chat/threads/`, `threads/create/`, `threads/<id>/messages/` |
| Поддержка | `/api/support/tickets/`, `tickets/<id>/messages/` |

## Опт

- `GET /api/products/?wholesale=true` — только оптовые позиции (`wholesale_price`, `wholesale_min_qty`)
- Оптовые уровни: `GET /api/products/<slug>/` → `wholesale_tiers`

## Платежи

По умолчанию включён `ManualProvider` (без Stripe-ключей): платёж создаётся, подтверждается через `PaymentService.confirm_payment` (или вебхуком). Для продакшена:

1. Заполнить `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` в `.env`.
2. Зарегистрировать вебхук Stripe на `https://ваш-домен/api/payments/webhook/stripe/`.
3. Комиссия платформы: `DEFAULT_COMMISSION_PERCENT` (10%) или индивидуальная `CommissionRule` для магазина.

## Примечания

- Кириллический поиск (`?q=`) работает и в SQLite: `core.lookups.UnicodeIContains` + переопределение SQLite `UPPER/LOWER` в `core.apps`.
- Для браузерного фронта понадобится CORS (`django-cors-headers`) — при подключении отдельного SPA добавьте его в `MIDDLEWARE`.

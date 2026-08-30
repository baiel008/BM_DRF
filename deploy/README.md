# HTTPS для бэка на бесплатном домене DuckDNS (фронт — только Vercel)

Бэк: AWS EC2 `13.53.42.60`, докер-compose (web=daphne, nginx, redis, db, worker).
Фронт: только Vercel, ходит на `https://bmmarket.duckdns.org` (api) и
`wss://bmmarket.duckdns.org/ws` (чат/уведомления).

DuckDNS уже привязан: `bmmarket.duckdns.org -> 13.53.42.60` (проверено).

## 1. Деплой бэка вместе с HTTPS

```bash
cd /opt/beauty/marketplace_drf        # куда клонирован BM_DRF
git pull

# токен DuckDNS — на сервер (секрет, не в git)
mkdir -p /etc/duckdns
echo 'd1dceecd-ba1c-43d8-b182-c89866fd0733' > /etc/duckdns/duckdns.token
chmod 700 /etc/duckdns && chmod 600 /etc/duckdns/duckdns.token
chmod +x deploy/*.sh

# обновить IP-запись DuckDNS (должно ответить OK) и положить в cron
bash deploy/duckdns.sh
(crontab -l 2>/dev/null; echo '*/5 * * * * /opt/beauty/marketplace_drf/deploy/duckdns.sh >/dev/null 2>&1') | crontab -

# выпуск сертификата + включение 443
bash deploy/letsencrypt.sh you@example.com
```

Проверка: `curl https://bmmarket.duckdns.org/api/products/` → JSON.

## 2. Продление (раз в ~2 месяца)

```bash
cd /opt/beauty/marketplace_drf
docker run --rm -v "$(pwd)/certbot/www:/var/www/certbot" \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  certbot/certbot renew --deploy-hook "docker compose exec nginx nginx -s reload"
```

или cron: `0 3 1 * *` … `--deploy-hook …`.

## 3. Vercel (фронт)

В `BM_FRONT` уже закоммичен `.env.production`:
```
VITE_API_URL=https://bmmarket.duckdns.org
VITE_WS_URL=wss://bmmarket.duckdns.org/ws
```
При пуше в `main` Vercel сам пересоберёт фронт с этими адресами.

## 4. CORS / ALLOWED_HOSTS

Сейчас на сервере `DEBUG=True` и дефолты — всё работает кросс-доменно.
Для боевой фазы задать в `.env` сервера явно:
```
DEBUG=False
ALLOWED_HOSTS=bmmarket.duckdns.org,13.53.42.60
CORS_ALLOWED_ORIGINS=https://<твой-front>.vercel.app,https://bmmarket.duckdns.org
CSRF_TRUSTED_ORIGINS=https://bmmarket.duckdns.org
```

## ВАЖНО

- Токен DuckDNS в git не лежит (только `/etc/duckdns/duckdns.token`).
- `certbot/` (сертификаты) в .gitignore.
- Фронт на сервер НЕ ставится — только Vercel.
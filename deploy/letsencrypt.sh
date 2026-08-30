#!/usr/bin/env bash
# Выпуск бесплатного Let's Encrypt-сертификата для bmmarket.duckdns.org (webroot).
# Создаёт заглушку, чтобы nginx поднялся с 443-блоком, затем выпускает реальный
# сертификат через certbot-контейнер и перезагружает nginx.
#
# Запуск с хоста, из каталога репо рядом с docker-compose.yml:
#   bash deploy/letsencrypt.sh your@email
#
# Переприменение для продления: достаточно поднять nginx (уже есть сертификат) и
#   docker run --rm -v "$(pwd)/certbot/www:/var/www/certbot" \
#     -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
#     certbot/certbot renew --deploy-hook "docker compose exec nginx nginx -s reload"
# (или расписание в cron — см. README.md)

set -euo pipefail

DOMAIN="bmmarket.duckdns.org"
EMAIL="${1:-admin@localhost}"
CONF_DIR="certbot/conf/live/$DOMAIN"

mkdir -p certbot/www "$CONF_DIR"

if [[ ! -f "$CONF_DIR/fullchain.pem" ]]; then
  echo "==> Заглушка (1 день), чтобы nginx смог подняться с 443..."
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$CONF_DIR/privkey.pem" \
    -out "$CONF_DIR/fullchain.pem" \
    -subj "/CN=$DOMAIN" 2>/dev/null
fi

echo "==> Поднимаем nginx..."
docker compose up -d nginx
docker run --rm --name bm-certbot \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL"

echo "==> Перезагружаем nginx..."
docker compose exec -T nginx nginx -s reload

echo "==> Готово. Проверка: curl https://$DOMAIN/api/products/"
echo "==> Продление: certbot renew через docker run (см. deploy/README.md), cron 1-го числа раз в 2 месяца с deploy-hook на reload nginx."
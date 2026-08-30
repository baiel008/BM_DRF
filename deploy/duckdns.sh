#!/usr/bin/env bash
# Обновление IP-записи DuckDNS (поддомен bmmarket -> IP бэка).
# Токен — секрет, хранится в /etc/duckdns/duckdns.token (в гит НЕ попадает).
# Cron: */5 * * * * /opt/beauty/marketplace_drf/deploy/duckdns.sh >/dev/null 2>&1

set -euo pipefail

DOMAIN="bmmarket"
TOKEN_FILE="/etc/duckdns/duckdns.token"

if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "Нет $TOKEN_FILE — положи туда токен DuckDNS (см. deploy/README.md)" >&2
  exit 1
fi

TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
[[ -n "$TOKEN" ]] || { echo "Пустой токен в $TOKEN_FILE" >&2; exit 1; }

RESP="$(curl -fsS "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=")"
echo "[$(date '+%F %T')] duckdns update: ${RESP}"
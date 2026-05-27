#!/bin/sh
set -eu

HTTP_CONF="/etc/nginx/templates/default-http.conf"
SSL_CONF="/etc/nginx/templates/default-ssl.conf"
TARGET_CONF="/etc/nginx/conf.d/default.conf"

: "${AGENT_API_UPSTREAM:=http://hems-agent-backend}"
: "${OPENVIKING_API_UPSTREAM:=http://openviking:1933}"

if [ -f /etc/nginx/tls/tls.crt ] && [ -f /etc/nginx/tls/tls.key ]; then
  envsubst '${AGENT_API_UPSTREAM} ${OPENVIKING_API_UPSTREAM}' < "${SSL_CONF}" > "${TARGET_CONF}"
  echo "[fls-web] TLS cert found, using HTTPS nginx config"
else
  envsubst '${AGENT_API_UPSTREAM} ${OPENVIKING_API_UPSTREAM}' < "${HTTP_CONF}" > "${TARGET_CONF}"
  echo "[fls-web] TLS cert not found, using HTTP nginx config"
fi

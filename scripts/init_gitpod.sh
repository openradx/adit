#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

ENV_DEV_FILE="$COMPOSE_DIR/.env.dev"

cp -a $PROJECT_DIR/example.env $ENV_DEV_FILE

BASE_URL=$(gp url 8000)
sed -i "s#\(BASE_URL=\).*#\1$BASE_URL#" $ENV_DEV_FILE
sed -i "s#\(DJANGO_CSRF_TRUSTED_ORIGINS=\).*#\1$BASE_URL#" $ENV_DEV_FILE

HOST=${BASE_URL#https://}
sed -i "s#DJANGO_ALLOWED_HOSTS=#&$HOST,#" $ENV_DEV_FILE
sed -i "s#DJANGO_INTERNAL_IPS=#&$HOST,#" $ENV_DEV_FILE

sed -i "s#\(FORCE_DEBUG_TOOLBAR=\).*#\1true#" $ENV_DEV_FILE

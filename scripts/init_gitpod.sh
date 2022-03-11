#!/usr/bin/env bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"
cp -a $PROJECT_DIR/example.env $PROJECT_DIR/compose/adit_dev/.env

BASE_URL=$(gp url 8000)
sed -i "s#\(BASE_URL=\).*#\1$BASE_URL#" compose/adit_dev/.env
sed -i "s#\(DJANGO_CSRF_TRUSTED_ORIGINS=\).*#\1$BASE_URL#" compose/adit_dev/.env

HOST=${BASE_URL#https://}
sed -i "s#DJANGO_ALLOWED_HOSTS=#&$HOST,#" compose/adit_dev/.env

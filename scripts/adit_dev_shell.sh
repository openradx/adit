#!/usr/bin/env bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

docker compose -f compose/adit_dev/docker-compose.dev.yml exec web python manage.py shell_plus

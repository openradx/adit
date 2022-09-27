#!/usr/bin/env bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

docker compose -f "$PROJECT_DIR/compose/adit_dev/docker-compose.dev.yml" up -d --build "$@"

docker compose -f "$PROJECT_DIR/compose/adit_dev/xnat1/docker-compose.yml" up -d
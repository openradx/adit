#!/usr/bin/env bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

docker-compose -f "$PROJECT_DIR/compose/adit_dev/docker-compose.dev.yml" exec web black ./adit
docker-compose -f "$PROJECT_DIR/compose/adit_dev/docker-compose.dev.yml" exec web isort ./adit

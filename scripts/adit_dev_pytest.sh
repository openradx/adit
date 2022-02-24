#!/usr/bin/env bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

# Same as `docker exec -it adit_dev_web_1 pytest "$@"`
docker-compose -f "$PROJECT_DIR/compose/adit_dev/docker-compose.dev.yml" exec web pytest "$@"

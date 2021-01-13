#!/bin/bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

docker-compose -f "$PROJECT_DIR/compose/adit_prod/docker-compose.prod.yml" up -d --build "$@"

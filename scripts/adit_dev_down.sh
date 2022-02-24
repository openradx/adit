#!/usr/bin/env bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

# To remove also all project volumes then execute with ./scripts/adit_dev_down.sh -v
docker-compose -f "$PROJECT_DIR/compose/adit_dev/docker-compose.dev.yml" down --remove-orphans "$@"

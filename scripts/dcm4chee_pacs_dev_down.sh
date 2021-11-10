#!/bin/bash

PROJECT_DIR="$(dirname $(dirname $(readlink -f $0)))"

docker-compose -p dcm4chee -f "$PROJECT_DIR/compose/dcm4chee_pacs_dev/docker-compose.yml" down --remove-orphans "$@"

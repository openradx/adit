#!/usr/bin/env bash

# https://github.com/microsoft/vscode-remote-release/issues/7958
# if [ "$CODESPACES" = true ]; then
#     export DOCKER_BUILDKIT=0
#     export BUILDKIT_INLINE_CACHE=0
# fi

ADIT_DEV_PROJ="adit_dev"
ADIT_PROD_PROJ="adit_prod"

SCRIPTS_DIR="$(dirname $(readlink -f $0))"
PROJECT_DIR="$(dirname $SCRIPTS_DIR)"
COMPOSE_DIR="$PROJECT_DIR/compose"

COMPOSE_COMMAND_BASE="docker compose -f '$COMPOSE_DIR/docker-compose.base.yml'"
COMPOSE_COMMAND_DEV="$COMPOSE_COMMAND_BASE -f '$COMPOSE_DIR/docker-compose.dev.yml' -p $ADIT_DEV_PROJ"
COMPOSE_COMMAND_PROD="$COMPOSE_COMMAND_BASE -f '$COMPOSE_DIR/docker-compose.prod.yml' -p $ADIT_PROD_PROJ"

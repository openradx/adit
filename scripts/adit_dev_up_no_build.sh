#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

eval $COMPOSE_COMMAND_DEV up --no-build --detach "$@"

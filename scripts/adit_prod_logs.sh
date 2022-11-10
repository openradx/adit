#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

eval $COMPOSE_COMMAND_PROD logs -f "$@"

#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

eval $COMPOSE_COMMAND_DEV exec --env DJANGO_SETTINGS_MODULE=adit.settings.test web pytest "$@"

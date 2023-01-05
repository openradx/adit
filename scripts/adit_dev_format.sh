#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

eval $COMPOSE_COMMAND_DEV exec web black ./adit
eval $COMPOSE_COMMAND_DEV exec web isort ./adit

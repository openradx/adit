#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

# Format Python code
eval $COMPOSE_COMMAND_DEV exec web black ./adit

# Sort Python imports
eval $COMPOSE_COMMAND_DEV exec web ruff . --fix --select I

# Format Django templates
eval $COMPOSE_COMMAND_DEV exec web djlint . --reformat

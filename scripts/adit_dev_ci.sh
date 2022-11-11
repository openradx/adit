#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

eval "$SCRIPTS_DIR/adit_dev_lint.sh"
eval "$SCRIPTS_DIR/adit_dev_cov.sh"

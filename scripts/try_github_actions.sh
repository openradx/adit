#!/usr/bin/env bash

source "$(dirname "$0")/common.sh"

if $ADIT_DEV_RUNNING; then
    echo "'adit_dev' containers must not be running when using this script."
    exit 1
fi

ACT_PATH="$PROJECT_DIR/bin/act"

cd $PROJECT_DIR

if [ ! -f "$ACT_PATH" ]; then
    echo "Installing act ..."
    curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
fi

echo "Running act ..."
# We use a custom image as the medium image of act does not support docker-compose
# see https://github.com/nektos/act/issues/112
eval $ACT_PATH -P ubuntu-latest=lucasalt/act_base:latest

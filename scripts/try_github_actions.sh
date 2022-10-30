#!/usr/bin/env bash

scripts_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
project_path=$( realpath "$scripts_path/.." )
act_path="$project_path/bin/act"

cd $project_path

if [ ! -f "$act_path" ]; then
    echo "Installing act ..."
    curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
fi

echo "Running act ..."
# We use a custom image as the medium image of act does not support docker-compose
# see https://github.com/nektos/act/issues/112
eval $act_path -P ubuntu-latest=lucasalt/act_base:latest
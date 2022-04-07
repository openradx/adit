#!/usr/bin/env bash

echo "Python packages:"
poetry show --outdated | grep --file=<(poetry show --tree | grep '^\w' | sed 's/^\([^ ]*\).*/^\1/')

echo "Javascript packages:"
npm outdated

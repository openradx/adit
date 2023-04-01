#!/usr/bin/env bash
# https://github.com/nodejs/node-gyp/issues/1526
node-gyp configure --release -- -f gyp.generator.compile_commands_json.py
mv Release/compile_commands.json ./
rmdir Release
EXTRA=$(ls */compile_commands.json)
echo "$EXTRA" | xargs rm
echo "$EXTRA" | xargs -n1 dirname | xargs rmdir
ESCAPED_FLAGS=$(echo | cc -Wp,-v -x c++ - -fsyntax-only 2>&1 |
    egrep '^ /' | sed 's/(framework directory)//' |
    sed 's/^ /-isystem/' | perl -pe 's/\//\\\//g' | tr '\n' ' ')
perl -i -pe 's/ -c / '"$ESCAPED_FLAGS"' -c /;' compile_commands.json
killall clangd

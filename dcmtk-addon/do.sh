#!/usr/bin/env bash

rm -rf ./build/
cmake -S. -Bbuild -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --target all

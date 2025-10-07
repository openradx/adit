#!/usr/bin/env bash

uv sync
uv run cli --install-completion
uv run cli init-workspace

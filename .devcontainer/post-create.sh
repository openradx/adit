#!/usr/bin/env bash

uv sync
uv run activate-global-python-argcomplete -y
uv run cli init-workspace

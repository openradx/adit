#!/usr/bin/env bash

uv sync
uv run typer --install-completion
uv run ./cli.py init-workspace

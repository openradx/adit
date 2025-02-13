#!/usr/bin/env python3

from pathlib import Path

from adit_radis_shared.maintenance_commands.init_workspace import init_workspace

if __name__ == "__main__":
    init_workspace(Path(__file__).resolve().parent)

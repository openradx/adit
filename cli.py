#! /usr/bin/env python3

from pathlib import Path
from typing import Annotated

import typer
from adit_radis_shared import cli_commands as commands
from adit_radis_shared import cli_helpers as helpers

helpers.PROJECT_ID = "adit"
helpers.ROOT_PATH = Path(__file__).resolve().parent

app = typer.Typer()

extra_args = {"allow_extra_args": True, "ignore_unknown_options": True}

app.command()(commands.init_workspace)
app.command()(commands.compose_up)
app.command()(commands.compose_down)
app.command()(commands.stack_deploy)
app.command()(commands.stack_rm)
app.command()(commands.lint)
app.command()(commands.format_code)
app.command(context_settings=extra_args)(commands.test)
app.command()(commands.show_outdated)
app.command()(commands.backup_db)
app.command()(commands.restore_db)
app.command()(commands.shell)
app.command()(commands.generate_certificate_files)
app.command()(commands.generate_certificate_chain)
app.command()(commands.generate_django_secret_key)
app.command()(commands.generate_secure_password)
app.command()(commands.generate_auth_token)
app.command()(commands.randomize_env_secrets)
app.command()(commands.try_github_actions)


@app.command()
def populate_orthancs(reset: Annotated[bool, typer.Option(help="Do not build images")] = False):
    """Populate Orthancs with example DICOMs"""

    cmd = f"{helpers.build_compose_cmd()} exec web python manage.py populate_orthancs"
    if reset:
        cmd += " --reset"

    helpers.execute_cmd(cmd)


if __name__ == "__main__":
    app()

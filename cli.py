#! /usr/bin/env python3
import os
import shutil
from glob import glob
from typing import Annotated

import typer
from adit_radis_shared.cli import commands
from adit_radis_shared.cli import helper as cli_helper

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

app.command()(commands.init_workspace)
app.command()(commands.randomize_env_secrets)
app.command()(commands.compose_build)
app.command()(commands.compose_pull)
app.command()(commands.compose_up)
app.command()(commands.compose_down)
app.command()(commands.stack_deploy)
app.command()(commands.stack_rm)
app.command()(commands.lint)
app.command()(commands.format_code)
app.command()(commands.test)
app.command()(commands.shell)
app.command()(commands.show_outdated)
app.command()(commands.db_backup)
app.command()(commands.db_restore)
app.command()(commands.generate_auth_token)
app.command()(commands.generate_secure_password)
app.command()(commands.generate_django_secret_key)
app.command()(commands.generate_certificate_chain)
app.command()(commands.generate_certificate_files)
app.command()(commands.upgrade_postgres_volume)
app.command()(commands.try_github_actions)


@app.command()
def populate_orthancs(
    reset: Annotated[bool, typer.Option(help="Clear Orthancs before populate")] = False,
):
    """Populate Orthancs from configured DICOM folders"""

    helper = cli_helper.CommandHelper()

    cmd = f"{helper.build_compose_cmd()} exec web python manage.py populate_orthancs"
    if reset:
        cmd += " --reset"

    helper.execute_cmd(cmd)


@app.command()
def copy_statics():
    """Copy JS and CSS dependencies from node_modules to static vendor folder"""
    print("Copying statics...")

    target_folder = "adit/upload/static/vendor"

    def copy_file(file: str, filename: str | None = None):
        if not filename:
            shutil.copy(file, target_folder)
        else:
            target_file = os.path.join(target_folder, filename)
            shutil.copy(file, target_file)

    for file in glob("node_modules/dcmjs/build/dcmjs.js*"):
        copy_file(file)
    for file in glob("node_modules/dicomweb-client/build/dicomweb-client.js*"):
        copy_file(file)
    for file in glob("node_modules/dicom-web-anonymizer/dist/dicom-web-anonymizer.*"):
        copy_file(file)

    print("Done.")


if __name__ == "__main__":
    app()

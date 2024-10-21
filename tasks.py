import os
import shutil
from glob import glob
from pathlib import Path

from adit_radis_shared import invoke_tasks
from adit_radis_shared.invoke_tasks import (  # noqa: F401
    backup_db,
    compose_down,
    compose_up,
    format,
    init_workspace,
    lint,
    reset_dev,
    restore_db,
    show_outdated,
    stack_deploy,
    stack_rm,
    test,
    try_github_actions,
    upgrade_adit_radis_shared,
    upgrade_postgresql,
    web_shell,
)
from invoke.context import Context
from invoke.tasks import task

invoke_tasks.PROJECT_NAME = "adit"
invoke_tasks.PROJECT_DIR = Path(__file__).resolve().parent


@task
def upgrade(ctx: Context):
    """Upgrade Python and JS packages"""
    ctx.run("poetry update", pty=True)
    ctx.run("npm update", pty=True)
    copy_statics(ctx)


@task
def reset_orthancs(ctx: Context, env: invoke_tasks.Environments = "dev"):
    """Reset Orthancs"""
    cmd = f"{invoke_tasks.build_compose_cmd(env)} exec web python manage.py reset_orthancs"
    ctx.run(cmd, pty=True)


@task
def copy_statics(ctx: Context):
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

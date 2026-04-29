#! /usr/bin/env python3
import os
import shlex
import shutil
from glob import glob
from pathlib import Path
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
def scale_mass_transfer_worker(
    replicas: Annotated[
        int,
        typer.Argument(
            help=(
                "Target replica count for the Docker Swarm mass transfer worker service. "
                "Use 0 to scale down and values > 0 to scale up."
            )
        ),
    ],
):
    if replicas < 0:
        typer.echo("replicas must be >= 0")
        raise typer.Exit(code=1)

    helper = cli_helper.CommandHelper()
    helper.prepare_environment()

    if not helper.is_production():
        typer.echo(
            "scale-mass-transfer-worker task can only be used in production environment. "
            "Check ENVIRONMENT setting in .env file."
        )
        raise typer.Exit(code=1)

    service_name = f"{helper.get_stack_name()}_mass_transfer_worker"
    helper.execute_cmd(f"docker service scale {service_name}={replicas}")


@app.command()
def configure_mass_transfer_worker_cron():
    helper = cli_helper.CommandHelper()
    helper.prepare_environment()

    if not helper.is_production():
        typer.echo(
            "configure-mass-transfer-worker-cron task can only be used in production environment. "
            "Check ENVIRONMENT setting in .env file."
        )
        raise typer.Exit(code=1)

    env = helper.load_config_from_env_file()
    # Inline cron block construction and validation so this command is self-contained.
    raw_up = env.get("MASS_TRANSFER_WORKER_REPLICAS") or "-1"
    raw_down = env.get("MASS_TRANSFER_WORKER_REPLICAS_DOWNSCALED") or "-1"
    try:
        up_replicas = int(raw_up)
        down_replicas = int(raw_down)
    except ValueError:
        typer.echo(
            f"Invalid int for MASS_TRANSFER_WORKER_REPLICAS(_DOWNSCALED): {raw_up} / {raw_down}"
        )
        raise typer.Exit(code=1)
    if up_replicas < 0 or down_replicas < 0:
        typer.echo("MASS_TRANSFER_WORKER_REPLICAS(_DOWNSCALED) must be >= 0")
        raise typer.Exit(code=1)

    up_cron = env.get("MASS_TRANSFER_WORKER_SCALE_UP_CRON") or ""
    down_cron = env.get("MASS_TRANSFER_WORKER_SCALE_DOWN_CRON") or ""
    if len(up_cron.split()) != 5:
        typer.echo(f"Invalid cron expression for MASS_TRANSFER_WORKER_SCALE_UP_CRON: {up_cron}")
        raise typer.Exit(code=1)
    if len(down_cron.split()) != 5:
        typer.echo(f"Invalid cron expression for MASS_TRANSFER_WORKER_SCALE_DOWN_CRON: {down_cron}")
        raise typer.Exit(code=1)

    project_root = shlex.quote(str(Path(helper.root_path)))
    logs_dir = shlex.quote(str(Path(helper.root_path) / "logs"))

    # Ensure logs directory exists
    Path(helper.root_path).joinpath("logs").mkdir(exist_ok=True)

    log_file = f"{logs_dir}/mass_transfer_worker_cron.log"

    scale_up_cmd = (
        f"cd {project_root} && /usr/local/bin/uv run cli scale-mass-transfer-worker {up_replicas}"
        f" >> {log_file} 2>&1"
    )
    scale_down_cmd = (
        f"cd {project_root} && /usr/local/bin/uv run cli scale-mass-transfer-worker {down_replicas}"
        f" >> {log_file} 2>&1"
    )

    cron_marker_start = "# ADIT_MASS_TRANSFER_WORKER_AUTOSCALE_START"
    cron_marker_end = "# ADIT_MASS_TRANSFER_WORKER_AUTOSCALE_END"
    cron_block = "\n".join(
        [
            cron_marker_start,
            f"{up_cron} {scale_up_cmd}",
            f"{down_cron} {scale_down_cmd}",
            cron_marker_end,
        ]
    )
    typer.echo("Executed: {}".format(cron_block))

    escaped_start = cron_marker_start.replace("/", "\\/")
    escaped_end = cron_marker_end.replace("/", "\\/")
    crontab_install_cmd = (
        "tmpfile=$(mktemp) && "
        f"(crontab -l 2>/dev/null | sed '/{escaped_start}/,/{escaped_end}/d'; "
        "cat <<'EOF'\n"
        f"{cron_block}\n"
        "EOF\n"
        ') > "$tmpfile" && '
        'crontab "$tmpfile" && '
        'rm "$tmpfile"'
    )
    helper.execute_cmd(crontab_install_cmd)


@app.command()
def remove_mass_transfer_worker_cron():
    helper = cli_helper.CommandHelper()
    helper.prepare_environment()

    if not helper.is_production():
        typer.echo(
            "remove-mass-transfer-worker-cron task can only be used in production environment. "
            "Check ENVIRONMENT setting in .env file."
        )
        raise typer.Exit(code=1)

    cron_marker_start = "# ADIT_MASS_TRANSFER_WORKER_AUTOSCALE_START"
    cron_marker_end = "# ADIT_MASS_TRANSFER_WORKER_AUTOSCALE_END"
    escaped_start = cron_marker_start.replace("/", "\\/")
    escaped_end = cron_marker_end.replace("/", "\\/")

    crontab_remove_cmd = (
        "tmpfile=$(mktemp) && "
        f"(crontab -l 2>/dev/null | sed '/{escaped_start}/,/{escaped_end}/d') > \"$tmpfile\" && "
        'crontab "$tmpfile" && '
        'rm "$tmpfile"'
    )
    helper.execute_cmd(crontab_remove_cmd)


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

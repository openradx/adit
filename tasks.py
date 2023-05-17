import sys
from glob import glob
from os import environ
from pathlib import Path
from shutil import copy
from typing import Literal

from dotenv import set_key
from invoke import task
from invoke.context import Context
from invoke.runners import Result

Environments = Literal["dev", "prod"]

proj_adit_dev = "adit_dev"
proj_adit_prod = "adit_prod"

project_dir = Path(__file__).resolve().parent
compose_dir = project_dir / "compose"


def compose_cmd(env: Environments = "dev"):
    base_compose_cmd = f"docker compose -f '{compose_dir}/docker-compose.base.yml'"
    if env == "dev":
        return f"{base_compose_cmd}  -f '{compose_dir}/docker-compose.dev.yml' -p {proj_adit_dev}"
    elif env == "prod":
        return f"{base_compose_cmd} -f '{compose_dir}/docker-compose.prod.yml' -p {proj_adit_prod}"
    else:
        raise ValueError(f"Unknown environment: {env}")


def check_dev_up(ctx: Context):
    result = ctx.run("docker compose ls", hide=True, warn=True)
    for line in result.stdout.splitlines():
        if line.startswith(proj_adit_dev) and line.find("running") != -1:
            return True
    return False


def run_cmd(ctx: Context, cmd: str) -> Result:
    print(f"Running: {cmd}")
    return ctx.run(cmd, pty=True)


@task
def compose_build(ctx: Context, env: Environments = "dev"):
    """Build ADIT containers in specified environment"""
    cmd = f"{compose_cmd(env)} build"
    run_cmd(ctx, cmd)


@task
def compose_up(ctx: Context, env: Environments = "dev", no_build: bool = False):
    """Start ADIT containers in specified environment"""
    build_opt = "--no-build" if no_build else "--build"
    cmd = f"{compose_cmd(env)} up {build_opt} --detach"
    run_cmd(ctx, cmd)


@task
def compose_down(ctx: Context, env: Environments = "dev"):
    """Stop ADIT containers in specified environment"""
    cmd = f"{compose_cmd(env)} down --remove-orphans"
    if env == "dev":
        # In dev environment, remove volumes as well
        cmd += " --volumes"
    run_cmd(ctx, cmd)


@task
def compose_restart(ctx: Context, env: Environments = "dev"):
    """Restart ADIT containers in specified environment"""
    cmd = f"{compose_cmd(env)} restart"
    run_cmd(ctx, cmd)


@task
def compose_logs(ctx: Context, env: Environments = "dev"):
    """Show logs of ADIT containers in specified environment"""
    cmd = f"{compose_cmd(env)} logs --follow"
    run_cmd(ctx, cmd)


@task
def format(ctx: Context):
    """Run formatting (black, ruff, djlint)"""
    # Format Python code
    black_cmd = "poetry run black ./adit"
    run_cmd(ctx, black_cmd)
    # Sort Python imports
    ruff_cmd = "poetry run ruff . --fix --select I"
    run_cmd(ctx, ruff_cmd)
    # Format Django templates
    djlint_cmd = "poetry run djlint . --reformat"
    run_cmd(ctx, djlint_cmd)


@task
def lint(ctx: Context):
    """Run linting (ruff and djlint)"""
    cmd_ruff = "poetry run ruff ."
    run_cmd(ctx, cmd_ruff)
    cmd_djlint = "poetry run djlint . --lint"
    run_cmd(ctx, cmd_djlint)


@task
def test(ctx: Context, cov: bool = False, path: str = "./adit"):
    """Run tests"""
    if not check_dev_up(ctx):
        sys.exit(
            "Integration tests need ADIT dev containers running.\nRun 'invoke compose-up' first."
        )

    cmd = f"{compose_cmd()} exec --env DJANGO_SETTINGS_MODULE=adit.settings.test web pytest "
    if cov:
        cmd += "--cov=adit "
    cmd += path
    run_cmd(ctx, cmd)


@task
def ci(ctx: Context):
    """Run continuous integration"""
    lint(ctx)
    test(ctx, cov=True)


@task
def reset_adit_dev(ctx: Context):
    """Reset ADIT dev container environment"""
    reset_orthancs_cmd = f"{compose_cmd()} exec web python manage.py reset_orthancs"
    run_cmd(ctx, reset_orthancs_cmd)
    flush_cmd = f"{compose_cmd()} exec web python manage.py flush --noinput"
    run_cmd(ctx, flush_cmd)
    populate_dev_db_cmd = f"{compose_cmd()} exec web python manage.py populate_dev_db"
    run_cmd(ctx, populate_dev_db_cmd)


@task
def adit_web_shell(ctx: Context, env: Environments = "dev"):
    """Open Python shell in ADIT web container of specified environment"""
    cmd = f"{compose_cmd(env)} exec web python manage.py shell_plus"
    run_cmd(ctx, cmd)


@task
def copy_statics(ctx: Context):
    """Copy JS and CSS dependencies from node_modules to static vendor folder"""
    print("Copying statics...")

    copy("node_modules/jquery/dist/jquery.js", "adit/static/vendor/")
    for file in glob("node_modules/bootstrap/dist/css/bootstrap.css*"):
        copy(file, "adit/static/vendor/")
    for file in glob("node_modules/bootstrap/dist/js/bootstrap.bundle.js*"):
        copy(file, "adit/static/vendor/")
    copy("node_modules/bootswatch/dist/flatly/bootstrap.css", "adit/static/vendor/")
    for file in glob("node_modules/alpinejs/dist/alpine*.js"):
        copy(file, "adit/static/vendor/")
    copy("node_modules/morphdom/dist/morphdom-umd.js", "adit/static/vendor/")
    copy("node_modules/htmx.org/dist/htmx.js", "adit/static/vendor/")
    copy("node_modules/htmx.org/dist/ext/ws.js", "adit/static/vendor/htmx-ws.js")
    copy(
        "node_modules/htmx.org/dist/ext/morphdom-swap.js",
        "adit/static/vendor/htmx-morphdom-swap.js",
    )


@task
def init_codespaces(ctx: Context):
    """Initialize Github Codespaces dev environment"""
    env_dev_file = f"{compose_dir}/.env.dev"
    copy(f"{project_dir}/example.env", env_dev_file)

    base_url = f"https://{environ['CODESPACE_NAME']}-8000.preview.app.github.dev"
    set_key(env_dev_file, "BASE_URL", base_url, quote_mode="never")
    set_key(env_dev_file, "DJANGO_CSRF_TRUSTED_ORIGINS", base_url, quote_mode="never")

    host = base_url.removeprefix("https://")
    set_key(env_dev_file, "DJANGO_ALLOWED_HOSTS", host, quote_mode="never")
    set_key(env_dev_file, "DJANGO_INTERNAL_IPS", host, quote_mode="never")

    set_key(env_dev_file, "FORCE_DEBUG_TOOLBAR", "true", quote_mode="never")


@task
def init_gitpod(ctx: Context):
    """Initialize Gitpod dev environment"""
    env_dev_file = f"{compose_dir}/.env.dev"
    copy(f"{project_dir}/example.env", env_dev_file)

    result = ctx.run("gp url 8000", hide=True)
    base_url = result.stdout.strip()
    set_key(env_dev_file, "BASE_URL", base_url, quote_mode="never")
    set_key(env_dev_file, "DJANGO_CSRF_TRUSTED_ORIGINS", base_url, quote_mode="never")

    host = base_url.removeprefix("https://")
    set_key(env_dev_file, "DJANGO_ALLOWED_HOSTS", host, quote_mode="never")
    set_key(env_dev_file, "DJANGO_INTERNAL_IPS", host, quote_mode="never")

    set_key(env_dev_file, "FORCE_DEBUG_TOOLBAR", "true", quote_mode="never")


@task
def show_outdated(ctx: Context):
    """Show outdated dependencies"""
    print("### Outdated Python dependencies ###")
    # TODO: Can use --top-level option after new Poetry release
    # https://github.com/python-poetry/poetry/pull/7415
    poetry_cmd = (
        "poetry show --outdated | grep --file=<(poetry show --tree | "
        "grep '^\w' | sed 's/^\([^ ]*\).*/^\\1/')"
    )
    result = run_cmd(ctx, poetry_cmd)
    print(result.stderr.strip())

    print("### Outdated NPM dependencies ###")
    npm_cmd = "npm outdated"
    run_cmd(ctx, npm_cmd)


@task
def poetry_sync(ctx: Context):
    """Sync Poetry dependencies (after manual changes in pyproject.toml)"""
    cmd = "poetry install --remove-untracked"
    run_cmd(ctx, cmd)


@task
def try_github_actions(ctx: Context):
    """Try Github Actions locally using Act"""
    if not check_dev_up(ctx):
        sys.exit("ADIT dev containers must be running. Run 'invoke compose-up' first.")
        return

    act_path = project_dir / "bin" / "act"

    if not act_path.exists():
        print("Installing act...")
        ctx.run("curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash")

    print("Running act...")
    # We use a custom image as the medium image of act does not support docker compose
    # see https://github.com/nektos/act/issues/112
    ctx.run(f"{act_path} -P ubuntu-latest=lucasalt/act_base:latest")

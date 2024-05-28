import os
import shutil
import sys
from os import environ
from pathlib import Path
from typing import Literal

from dotenv import set_key
from invoke.context import Context
from invoke.tasks import task

Environments = Literal["dev", "prod", "test"]
Profile = Literal["full", "web"]

stack_name_dev = "adit_dev"
stack_name_prod = "adit_prod"

postgres_dev_volume = f"{stack_name_dev}_postgres_data"
postgres_prod_volume = f"{stack_name_prod}_postgres_data"

project_dir = Path(__file__).resolve().parent
compose_dir = project_dir / "compose"

compose_file_base = compose_dir / "docker-compose.base.yml"
compose_file_dev = compose_dir / "docker-compose.dev.yml"
compose_file_prod = compose_dir / "docker-compose.prod.yml"

###
# Helper functions
###


def get_stack_name(env: Environments):
    if env == "dev":
        return stack_name_dev
    elif env == "prod":
        return stack_name_prod
    else:
        raise ValueError(f"Unknown environment: {env}")


def get_postgres_volume(env: Environments):
    if env == "dev":
        return postgres_dev_volume
    elif env == "prod":
        return postgres_prod_volume
    else:
        raise ValueError(f"Unknown environment: {env}")


def build_compose_cmd(env: Environments):
    base_compose_cmd = f"docker compose -f '{compose_file_base}'"
    stack_name = get_stack_name(env)
    if env == "dev":
        return f"{base_compose_cmd} -f '{compose_file_dev}' -p {stack_name}"
    elif env == "prod":
        return f"{base_compose_cmd} -f '{compose_file_prod}' -p {stack_name}"
    else:
        raise ValueError(f"Unknown environment: {env}")


def check_compose_up(ctx: Context, env: Environments):
    stack_name = get_stack_name(env)
    result = ctx.run("docker compose ls", hide=True, warn=True)
    assert result and result.ok
    for line in result.stdout.splitlines():
        if line.startswith(stack_name) and line.find("running") != -1:
            return True
    return False


def find_running_container_id(ctx: Context, env: Environments, name: str):
    stack_name = get_stack_name(env)
    sep = "-" if env == "dev" else "_"
    cmd = f"docker ps -q -f name={stack_name}{sep}{name} -f status=running"
    cmd += " | head -n1"
    result = ctx.run(cmd, hide=True, warn=True)
    if result and result.ok:
        container_id = result.stdout.strip()
        if container_id:
            return container_id
    return None


def get_settings_module(env: Environments):
    if env == "dev":
        return "adit.settings.development"
    elif env == "prod":
        return "adit.settings.production"
    elif env == "test":
        return "adit.settings.test"
    else:
        raise ValueError(f"Unknown environment: {env}")


def confirm(question: str) -> bool:
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    while True:
        sys.stdout.write(f"{question} [y/N] ")
        choice = input().lower()
        if choice == "":
            return False
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


###
# Tasks
###


@task
def compose_build(ctx: Context, env: Environments = "dev"):
    """Build ADIT image for specified environment"""
    cmd = f"{build_compose_cmd(env)} build"
    ctx.run(cmd, pty=True)


@task
def compose_up(
    ctx: Context,
    env: Environments = "dev",
    no_build: bool = False,
    profile: Profile = "full",
):
    """Start ADIT containers in specified environment"""
    build_opt = "--no-build" if no_build else "--build"
    cmd = f"{build_compose_cmd(env)} --profile {profile} up {build_opt} --detach"
    ctx.run(cmd, pty=True)


@task
def compose_down(
    ctx: Context,
    env: Environments = "dev",
    profile: Profile = "full",
    cleanup: bool = False,
):
    """Stop ADIT containers in specified environment"""
    cmd = f"{build_compose_cmd(env)} --profile {profile} down"
    if cleanup:
        cmd += " --remove-orphans --volumes"
    ctx.run(cmd, pty=True)


@task
def compose_restart(ctx: Context, env: Environments = "dev", service: str | None = None):
    """Restart ADIT containers in specified environment"""
    cmd = f"{build_compose_cmd(env)} restart"
    if service:
        cmd += f" {service}"
    ctx.run(cmd, pty=True)


@task
def compose_logs(
    ctx: Context,
    env: Environments = "dev",
    service: str | None = None,
    follow: bool = False,
    since: str | None = None,
    until: str | None = None,
    tail: int | None = None,
):
    """Show logs of ADIT containers in specified environment"""
    cmd = f"{build_compose_cmd(env)} logs"
    if service:
        cmd += f" {service}"
    if follow:
        cmd += " --follow"
    if since:
        cmd += f" --since {since}"
    if until:
        cmd += f" --until {until}"
    if tail:
        cmd += f" --tail {tail}"
    ctx.run(cmd, pty=True)


@task
def stack_deploy(ctx: Context, env: Environments = "prod", build: bool = False):
    """Deploy the stack to Docker Swarm (prod by default!). Optional build it before."""
    if build:
        compose_build(ctx, env)

    stack_name = get_stack_name(env)
    suffix = f"-c {compose_file_base}"
    if env == "dev":
        suffix += f" -c {compose_file_dev} {stack_name}"
    elif env == "prod":
        suffix += f" -c {compose_file_prod} {stack_name}"
    else:
        raise ValueError(f"Unknown environment: {env}")

    cmd = f"docker stack deploy {suffix}"
    ctx.run(cmd, pty=True)


@task
def stack_rm(ctx: Context, env: Environments = "prod"):
    """Remove the stack from Docker Swarm (prod by default!)."""
    stack_name = get_stack_name(env)
    cmd = f"docker stack rm {stack_name}"
    ctx.run(cmd, pty=True)


@task
def make_migrations(ctx: Context, env: Environments = "dev"):
    """Make Django migrations (optionally of the test app)"""
    settings_module = get_settings_module(env)
    cmd = f"django-admin makemigrations --settings={settings_module}"
    ctx.run(cmd, pty=True)


@task
def format(ctx: Context):
    """Format the source code with ruff and djlint"""
    # Format Python code
    format_code_cmd = "poetry run ruff format ."
    ctx.run(format_code_cmd, pty=True)
    # Sort Python imports
    sort_imports_cmd = "poetry run ruff check . --fix --select I"
    ctx.run(sort_imports_cmd, pty=True)
    # Format Django templates
    format_templates_cmd = "poetry run djlint . --reformat"
    ctx.run(format_templates_cmd, pty=True)


@task
def lint(ctx: Context):
    """Lint the source code (ruff, djlint, pyright)"""
    cmd_ruff = "poetry run ruff check ."
    ctx.run(cmd_ruff, pty=True)
    cmd_djlint = "poetry run djlint . --lint"
    ctx.run(cmd_djlint, pty=True)
    cmd_pyright = "poetry run pyright"
    ctx.run(cmd_pyright, pty=True)


@task
def test(
    ctx: Context,
    path: str | None = None,
    cov: bool | str = False,
    html: bool = False,
    keyword: str | None = None,
    mark: str | None = None,
    stdout: bool = False,
    failfast: bool = False,
):
    """Run the test suite"""
    if not check_compose_up(ctx, "dev"):
        sys.exit(
            "Integration tests need ADIT dev containers running.\nRun 'invoke compose-up' first."
        )

    cmd = (
        f"{build_compose_cmd('dev')} exec "
        "--env DJANGO_SETTINGS_MODULE=adit.settings.test web pytest "
    )
    if cov:
        cmd += "--cov "
        if isinstance(cov, str):
            cmd += f"={cov} "
        if html:
            cmd += "--cov-report=html"
    if keyword:
        cmd += f"-k {keyword} "
    if mark:
        cmd += f"-m {mark} "
    if stdout:
        cmd += "-s "
    if failfast:
        cmd += "-x "
    if path:
        cmd += path
    ctx.run(cmd, pty=True)


@task
def ci(ctx: Context):
    """Run the continuous integration (linting and tests)"""
    lint(ctx)
    test(ctx, cov=True)


@task
def reset_dev(ctx: Context):
    """Reset dev container environment"""
    # Reset Orthancs
    reset_orthancs(ctx, "dev")
    # Wipe the database
    flush_cmd = f"{build_compose_cmd('dev')} exec web python manage.py flush --noinput"
    ctx.run(flush_cmd, pty=True)
    # Re-populate the database with users and groups
    populate_cmd = f"{build_compose_cmd('dev')} exec web python manage.py populate_users_and_groups"
    populate_cmd += " --users 20 --groups 3"
    ctx.run(populate_cmd, pty=True)
    # Re-populate the database with example data
    populate_cmd = f"{build_compose_cmd('dev')} exec web python manage.py populate_data"
    ctx.run(populate_cmd, pty=True)


@task
def reset_orthancs(ctx: Context, env: Environments = "dev"):
    """Reset Orthancs"""
    cmd = f"{build_compose_cmd(env)} exec web python manage.py reset_orthancs"
    ctx.run(cmd, pty=True)


@task
def adit_web_shell(ctx: Context, env: Environments = "dev"):
    """Open Python shell in ADIT web container of specified environment"""
    cmd = f"{build_compose_cmd(env)} exec web python manage.py shell_plus"
    ctx.run(cmd, pty=True)


@task
def init_workspace(ctx: Context):
    """Initialize workspace for Github Codespaces or Gitpod"""
    env_dev_file = f"{project_dir}/.env.dev"
    if os.path.isfile(env_dev_file):
        print("Workspace already initialized (.env.dev file exists).")
        return

    shutil.copy(f"{project_dir}/example.env", env_dev_file)

    def modify_env_file(domain: str | None = None):
        if domain:
            url = f"https://{domain}"
            hosts = f".localhost,127.0.0.1,[::1],{domain}"
            set_key(env_dev_file, "DJANGO_CSRF_TRUSTED_ORIGINS", url, quote_mode="never")
            set_key(env_dev_file, "DJANGO_ALLOWED_HOSTS", hosts, quote_mode="never")
            set_key(env_dev_file, "DJANGO_INTERNAL_IPS", hosts, quote_mode="never")
            set_key(env_dev_file, "SITE_BASE_URL", url, quote_mode="never")
            set_key(env_dev_file, "SITE_DOMAIN", domain, quote_mode="never")

        set_key(env_dev_file, "FORCE_DEBUG_TOOLBAR", "true", quote_mode="never")

    if environ.get("CODESPACE_NAME"):
        # Inside GitHub Codespaces
        domain = f"{environ['CODESPACE_NAME']}-8000.preview.app.github.dev"
        modify_env_file(domain)
    elif environ.get("GITPOD_WORKSPACE_ID"):
        # Inside Gitpod
        result = ctx.run("gp url 8000", hide=True, pty=True)
        assert result and result.ok
        domain = result.stdout.strip().removeprefix("https://")
        modify_env_file(domain)
    else:
        # Inside some local environment
        modify_env_file()


@task
def show_outdated(ctx: Context):
    """Show outdated dependencies"""
    print("### Outdated Python dependencies ###")
    poetry_cmd = "poetry show --outdated --top-level"
    result = ctx.run(poetry_cmd, pty=True)
    assert result and result.ok
    print(result.stderr.strip())

    print("### Outdated NPM dependencies ###")
    npm_cmd = "npm outdated"
    ctx.run(npm_cmd, pty=True)


@task
def upgrade(ctx: Context):
    """Upgrade Python and JS packages"""
    ctx.run("poetry update", pty=True)


@task
def try_github_actions(ctx: Context):
    """Try Github Actions locally using Act"""
    act_path = project_dir / "bin" / "act"
    if not act_path.exists():
        print("Installing act...")
        ctx.run(
            "curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash",
            hide=True,
            pty=True,
        )
    ctx.run(f"{act_path} -P ubuntu-latest=catthehacker/ubuntu:act-latest", pty=True)


@task
def purge_celery(
    ctx: Context,
    env: Environments = "dev",
    queues: str = "default_queue,dicom_task_queue",
    force=False,
):
    """Purge Celery queues"""
    settings = "adit.settings.production" if env == "prod" else "adit.settings.development"
    web_container_id = find_running_container_id(ctx, env, "web")
    cmd = (
        f"docker exec --env DJANGO_SETTINGS_MODULE={settings} "
        f"{web_container_id} celery -A adit purge -Q {queues}"
    )
    if force:
        cmd += " -f"
    ctx.run(cmd, pty=True)


@task
def backup_db(ctx: Context, env: Environments = "prod"):
    """Backup database

    For backup location see setting DBBACKUP_STORAGE_OPTIONS
    For possible commands see:
    https://django-dbbackup.readthedocs.io/en/master/commands.html
    """
    settings = "adit.settings.production" if env == "prod" else "adit.settings.development"
    web_container_id = find_running_container_id(ctx, env, "web")
    cmd = (
        f"docker exec --env DJANGO_SETTINGS_MODULE={settings} "
        f"{web_container_id} ./manage.py dbbackup --clean -v 2"
    )
    ctx.run(cmd, pty=True)


@task
def restore_db(ctx: Context, env: Environments = "prod"):
    """Restore database from backup"""
    settings = "adit.settings.production" if env == "prod" else "adit.settings.development"
    web_container_id = find_running_container_id(ctx, env, "web")
    cmd = (
        f"docker exec --env DJANGO_SETTINGS_MODULE={settings} "
        f"{web_container_id} ./manage.py dbrestore"
    )
    ctx.run(cmd, pty=True)


@task
def bump_version(ctx: Context, rule: Literal["patch", "minor", "major"]):
    """Bump version, create a tag, commit and push to GitHub"""
    result = ctx.run("git status --porcelain", hide=True, pty=True)
    assert result and result.ok
    if result.stdout.strip():
        print("There are uncommitted changes. Aborting.")
        sys.exit(1)

    ctx.run(f"poetry version {rule}", pty=True)
    ctx.run("git add pyproject.toml", pty=True)
    ctx.run("git commit -m 'Bump version'", pty=True)
    ctx.run('git tag -a v$(poetry version -s) -m "Release v$(poetry version -s)"', pty=True)
    ctx.run("git push --follow-tags", pty=True)


@task
def upgrade_postgresql(ctx: Context, env: Environments = "dev", version: str = "latest"):
    print(f"Upgrading PostgreSQL database in {env} environment to {version}.")
    print("Cave, make sure the whole stack is not stopped. Otherwise this will corrupt data!")
    if confirm("Are you sure you want to proceed?"):
        print("Starting docker container that upgrades the database files.")
        print("Watch the output if everything went fine or if any further steps are necessary.")
        volume = get_postgres_volume(env)
        ctx.run(
            f"docker run -e POSTGRES_PASSWORD=postgres -v {volume}:/var/lib/postgresql/data "
            f"pgautoupgrade/pgautoupgrade:{version}",
            pty=True,
        )
    else:
        print("Cancelled")

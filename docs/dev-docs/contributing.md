# Contributing to Our Project

This document describes how to set up a development environment for ADIT, the tooling we use and the conventions contributions are expected to follow. We follow the Google Python Style Guide to keep the codebase consistent and readable.

**Code Style:**
We adhere to the Google Python Style [Guide](https://google.github.io/styleguide/pyguide.html). The enforced configuration lives in `pyproject.toml`:

- **Ruff** for linting and formatting: line length 100, rule sets `E`, `F`, `I`, `DJ`, `UP` (migrations and notebooks are excluded)
- **pyright** in `basic` mode (migrations excluded)
- **djlint** with the `django` profile and a line length of 120 for templates

Run `uv run cli lint` to check all three and `uv run cli format-code` to format.

## Getting Started

This repository includes a [Dev Container](https://code.visualstudio.com/docs/devcontainers/create-dev-container). The **Dev Container** is a Docker container that provides the development environment (VS Code, Git, Docker CLI, Node.js, Python tools). It uses [Docker outside of Docker](https://github.com/devcontainers/features/tree/main/src/docker-outside-of-docker): the host's Docker socket is mounted into the Dev Container, so ADIT's application containers are started on the host's Docker daemon and run next to the Dev Container, not inside it. This gives all developers an identical toolchain while keeping the Docker Compose commands the same as outside the Dev Container.
If you open the project in VS Code after cloning, you should see a prompt:

“Reopen in Dev Container”

Click it, and VS Code will automatically build and open the development environment.

### Installation

```terminal
git clone https://github.com/openradx/adit.git
cd adit
uv sync  # installs Python dependencies into a virtual environment
cp ./example.env ./.env  # adjust the environment variables to your needs
uv run pre-commit install  # installs the Git hooks
uv run cli compose-up -- --watch  # builds and starts the Docker containers
```

The development server will start at <http://localhost:8000>. The placeholder secrets in `.env` are fine for local development; `uv run cli generate-django-secret-key`, `generate-secure-password` and `generate-auth-token` print real ones if you need them. Do not wrap values in quotes (see the note at the top of `example.env`).

`--watch` is required: it syncs your working tree into the containers on every file change (the dev servers restart automatically) and rebuilds the images when `pyproject.toml` changes (see `docker-compose.dev.yml`). Without it the containers keep running the code they were built with.

The `.env` file is passed to the containers via `env_file`, so edits to it need only `uv run cli compose-up -- --watch` again, not a rebuild. `WAIT_POSTGRES_TIMEOUT` (default 180 seconds) limits how long the web and worker containers wait for PostgreSQL on startup.

### Pre-commit Hooks

`uv run pre-commit install` registers the hooks from `.pre-commit-config.yaml`: ruff (check with autofix) and ruff-format, djlint (reformat and lint), pyright, `uv lock --check` (for the root project and `adit-client`), plus the usual whitespace, YAML/TOML/JSON, and merge-conflict checks. The tool versions come from `uv.lock`. Run them on demand with `uv run pre-commit run --all-files`.

### Running Tests

Tests run inside the `web` container, so the dev containers must be up:

```terminal
uv run cli test                       # run all tests
uv run cli test -- -k "test_name"     # run tests matching a name
uv run cli test -- adit/core/tests/   # run tests in a directory
uv run cli test -- --cov              # run with coverage
uv run cli test -- -m acceptance      # run only the Playwright acceptance tests
```

Everything after `--` is passed to pytest. Warnings are treated as errors (`filterwarnings = ["error", ...]` in `pyproject.toml`), so a new deprecation warning fails the suite; add an explicit ignore there only when it cannot be fixed.

### Updating Your Development Environment

**Pull latest changes**:

```terminal
git pull origin main
uv sync  # update dependencies
uv run cli compose-up -- --watch  # restart containers (migrations run automatically)
```

**After pulling changes**:

- Migrations run as part of the web container's startup command (`./manage.py migrate` in `docker-compose.dev.yml`), together with the example data setup
- If containers fail to start due to dependency or image changes, rebuild them:

  ```terminal
  uv run cli compose-build && uv run cli compose-up -- --watch
  ```

- For major database schema changes, consider backing up first: `uv run cli db-backup`

!!! note "Development vs Production"

    **Development**: Use `uv run cli compose-up -- --watch` for local development

    **Production**: Use `uv run cli stack-deploy` for production deployment with Docker Swarm

## Reporting Issues

If you encounter bugs or have feature requests, please open an issue on GitHub. Include as much detail as possible, including steps to reproduce the issue.

## Making Changes

1. Fork the repository and create a new branch for your feature or bug fix.
2. Make your changes and ensure that they adhere to the Google Python Style Guide and pass `uv run cli lint` (the pre-commit hooks run the same tools).
3. Write tests for your changes and ensure that all tests pass (`uv run cli test`).
4. Commit your changes to a new branch with a clear and descriptive commit message.
5. Push your changes to your forked repository and create a pull request against the main repository.
6. Ensure that your pull request is linked to an issue in the main repository.

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 license.

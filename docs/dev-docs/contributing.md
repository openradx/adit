# Contributing to Our Project

We're excited that you're interested in contributing to our project! This document outlines the guidelines for contributing to our codebase. We follow the Google Python Style Guide to maintain consistency and readability across our project.

**Code Style:**
We adhere to the Google Python Style [Guide](https://google.github.io/styleguide/pyguide.html).

## Getting Started

This repository includes a [Dev Container](https://code.visualstudio.com/docs/devcontainers/create-dev-container). The **Dev Container** is a Docker container that provides the development environment (VS Code, Git, Docker CLI, Node.js, Python tools). It uses Docker-in-Docker to run the application containers inside it. This ensures all developers have identical environments and can manage ADIT's multi-container setup seamlessly.
If you open the project in VS Code after cloning, you should see a prompt:

“Reopen in Dev Container”

Click it, and VS Code will automatically build and open the development environment.

### Installation

```terminal
git clone https://github.com/openradx/adit.git
cd adit
uv sync  # installs Python dependencies into a virtual environment
cp ./example.env ./.env  # copy environment template (adjust DJANGO_SECRET_KEY and TOKEN_AUTHENTICATION_SALT)
uv run cli compose-up  # builds and starts Docker containers
```

The development server will start at <http://localhost:8000>.

**Initial setup**: The `compose-up` command automatically runs migrations, creates example users/groups, and populates test Orthanc instances with sample data.

**File watching**: Code changes auto-reload the server. Dependency changes (pyproject.toml) trigger container rebuilds.

### Updating Your Development Environment

**Pull latest changes**:

```terminal
git pull origin main
uv sync  # update dependencies
uv run cli compose-up  # restart containers (migrations run automatically)
```

**After pulling changes**:

- Migrations run automatically on container startup
- If containers don't start, rebuild: `uv run cli compose-build && uv run cli compose-up`
- For major database schema changes, consider backing up first: `uv run cli db-backup`

**Dependency updates**:

- Python packages are updated via `uv sync` when pyproject.toml changes
- Docker images update via `uv run cli compose-pull` (base images)

File changes will be automatically detected and the servers will be restarted. When library
dependencies are changed, the containers will automatically be rebuilt and restarted.

!!! note "Development vs Production"

**Development**: Use `uv run cli compose-up` for local development
**Production**: Use `uv run cli stack-deploy` for production deployment with Docker Swarm

## Reporting Issues

If you encounter bugs or have feature requests, please open an issue on GitHub. Include as much detail as possible, including steps to reproduce the issue.

## Making Changes

1. Fork the repository and create a new branch for your feature or bug fix.
2. Make your changes and ensure that they adhere to the Google Python Style Guide.
3. Write tests for your changes and ensure that all tests pass.
4. Commit your changes to a new branch with a clear and descriptive commit message.
5. Push your changes to your forked repository and create a pull request against the main repository.
6. Ensure that your pull request is linked to an issue in the main repository.

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 license.

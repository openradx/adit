# Contributing to ADIT

Thank you for your interest in contributing! Quick start:

```terminal
git clone https://github.com/openradx/adit.git && cd adit
uv sync                            # install Python dependencies
cp ./example.env ./.env            # adjust the environment variables to your needs
uv run cli compose-up -- --watch   # build and start the dev containers on http://localhost:8000
uv run cli lint                    # ruff, pyright, djlint
uv run cli test                    # pytest inside the web container
```

The full developer guide (dev container, pre-commit hooks, code style, testing, updating your
environment) is in [docs/dev-docs/contributing.md](docs/dev-docs/contributing.md), also published
at <https://openradx.github.io/adit/dev-docs/contributing/>.

## Reporting Issues

If you encounter bugs or have feature requests, please open an issue on GitHub. Include as much
detail as possible, including steps to reproduce the issue.

## Making Changes

1. Fork the repository and create a new branch for your feature or bug fix.
2. Make your changes and make sure `uv run cli lint` and `uv run cli test` pass.
3. Commit with a clear and descriptive commit message.
4. Push to your fork and open a pull request against `main`, linked to an issue where possible.

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 license.

# Contributing to Our Project

We're excited that you're interested in contributing to our project! This document outlines the
guidelines for contributing to our codebase. We follow the Google Python Style Guide to maintain
consistency and readability across our project.

Code Style
We adhere to the Google Python Style [Guide](https://google.github.io/styleguide/pyguide.html).

## Getting Started

```terminal
git clone https://github.com/openradx/adit.git
cd adit
uv sync
cp ./example.env ./.env  # adjust the environment variables to your needs
uv run cli compose-up -- --watch
```

The development server of the example project will be started on <http://localhost:8000>

File changes will be automatically detected and the servers will be restarted. When library
dependencies are changed, the containers will automatically be rebuilt and restarted.

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

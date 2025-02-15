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
uv run ./cli.py compose-up
```

The development server of the example project will be started on <http://localhost:8000>

If a library dependency is changed, the containers need to be rebuilt (e.g. by running
`uv run ./cli.py compose-down && uv run ./cli.py compose-up`).

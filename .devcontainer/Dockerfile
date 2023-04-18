FROM mcr.microsoft.com/devcontainers/python:3.10

USER vscode

RUN curl -sSL https://install.python-poetry.org | python - && \
    $HOME/.local/bin/poetry config virtualenvs.in-project true

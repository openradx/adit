FROM mcr.microsoft.com/devcontainers/python:3.10

USER vscode

RUN curl -sSL https://install.python-poetry.org | python - && \
    /home/vscode/.local/bin/poetry config virtualenvs.in-project true

# https://github.com/microsoft/vscode-remote-release/issues/7958#issuecomment-1422291636
ENV DOCKER_BUILDKIT=0

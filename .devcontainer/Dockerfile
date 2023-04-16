FROM mcr.microsoft.com/devcontainers/universal:2.2.9

USER codespace

RUN curl -sSL https://install.python-poetry.org | python - && \
    poetry config virtualenvs.in-project true

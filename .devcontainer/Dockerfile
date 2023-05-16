FROM mcr.microsoft.com/devcontainers/python:3.10

# Install dependency to make bash completion work with invoke
RUN apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install -y bash-completion && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

USER vscode

ENV BASH_COMPLETION_DIR ~/.local/share/bash-completion/completions

RUN echo $BASH_COMPLETION_DIR

# pipx is already installed in the base devcontainers Python image
RUN pipx install invoke && \
  invoke --print-completion-script=bash > $HOME/.bash_completion

RUN curl -sSL https://install.python-poetry.org | python - && \
  $HOME/.local/bin/poetry config virtualenvs.in-project true

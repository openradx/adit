FROM mcr.microsoft.com/devcontainers/python:3.12

# Install dependency to make bash completion work with invoke
RUN apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install -y bash-completion && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

USER vscode

# pipx is already installed in the base devcontainers Python image
RUN pipx install invoke && \
  invoke --print-completion-script=bash >> ~/.bash_completion

RUN pipx install poetry && \
  poetry completions bash >> ~/.bash_completion

FROM mcr.microsoft.com/devcontainers/python:3.13

USER root

# Install system dependencies
# - bash-completion for shell completions of invoke
# - gettext for Django translations
# - postgresql-common for the apt.postgresql.org.sh script
# - postgresql-client-17 for a current version of psql
RUN sudo apt-get update \
  && apt-get install -y --no-install-recommends \
  bash-completion \
  gettext \
  postgresql-common \
  && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
  && apt-get install -y --no-install-recommends \
  postgresql-client-17 \
  && rm -rf /var/lib/apt/lists/*

USER vscode

# pipx is already installed in the base devcontainers Python image
RUN pipx install invoke \
  && invoke --print-completion-script=bash >> ~/.bash_completion \
  pipx uninstall invoke

RUN pipx install poetry \
  && poetry completions bash >> ~/.bash_completion

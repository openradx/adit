FROM mcr.microsoft.com/devcontainers/python:3.13

USER root

# Install system dependencies
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

RUN pipx install poetry \
  && poetry completions bash >> ~/.bash_completion

FROM mcr.microsoft.com/devcontainers/python:3.15-bookworm@sha256:043d2843b67306fad755de26cbf3effaf680109268839c152fdb767d77c966d9

USER root

# Install system dependencies
# - gettext for Django translations
# - postgresql-common for the apt.postgresql.org.sh script
# - postgresql-client-17 for a current version of psql
# Make sure to match the version of the postgres service in the compose file!
RUN sudo apt-get update \
  && apt-get install -y --no-install-recommends \
  gettext \
  postgresql-common \
  && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
  && apt-get install -y --no-install-recommends \
  postgresql-client-17 \
  && rm -rf /var/lib/apt/lists/*

USER vscode

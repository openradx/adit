FROM mcr.microsoft.com/devcontainers/python:3.11

USER root

# Install dependency to make bash completion work with invoke
RUN apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install -y bash-completion && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Install Vespa CLI
ADD https://github.com/vespa-engine/vespa/releases/download/v8.184.20/vespa-cli_8.184.20_linux_amd64.tar.gz /tmp/vespa-cli.tar.gz
RUN  mkdir /tmp/vespa-cli \
  && tar -xzf /tmp/vespa-cli.tar.gz -C /tmp/vespa-cli --strip-components 1 \
  && cp -r /tmp/vespa-cli/bin/* /usr/local/bin/ \
  && cp -r /tmp/vespa-cli/share/* /usr/local/share/ \
  && rm -rf /tmp/vespa-cli.tar.gz /tmp/vespa-cli

USER vscode

# pipx is already installed in the base devcontainers Python image
RUN pipx install invoke && \
  invoke --print-completion-script=bash >> ~/.bash_completion

RUN pipx install poetry && \
  poetry completions bash >> ~/.bash_completion && \
  poetry config virtualenvs.in-project true

FROM gitpod/workspace-python-3.11

USER gitpod

ENV NVM_DIR $HOME/.nvm
ENV NODE_VERSION 18.16.0

RUN mkdir $NVM_DIR && \ 
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash && \
  . $NVM_DIR/nvm.sh && \
  nvm install $NODE_VERSION && \
  nvm alias default $NODE_VERSION && \
  nvm use default

RUN python3 -m pip install --user pipx && \
  python3 -m pipx ensurepath && \
  python3 -m pipx install invoke && \
  invoke --print-completion-script=bash >> $HOME/.bash_completion

ENV NODE_PATH $NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH $NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

# Poetry is already installed in the base Gitpod Python image,
# but we need to upgrade it
RUN poetry self update && \
  poetry completions bash >> ~/.bash_completion && \
  poetry config virtualenvs.in-project true

# Install Vespa CLI
ADD https://github.com/vespa-engine/vespa/releases/download/v8.184.20/vespa-cli_8.184.20_linux_amd64.tar.gz /tmp/vespa-cli.tar.gz
RUN  mkdir /tmp/vespa-cli \
  && tar -xzf /tmp/vespa-cli.tar.gz -C /tmp/vespa-cli --strip-components 1 \
  && cp -r /tmp/vespa-cli/bin/* /usr/local/bin/ \
  && cp -r /tmp/vespa-cli/share/* /usr/local/share/ \
  && rm -rf /tmp/vespa-cli.tar.gz /tmp/vespa-cli

FROM gitpod/workspace-python-3.10

ENV NVM_DIR $HOME/.nvm
ENV NODE_VERSION 18.16.0

RUN mkdir $NVM_DIR && \ 
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash && \
  . $NVM_DIR/nvm.sh && \
  nvm install $NODE_VERSION && \
  nvm alias default $NODE_VERSION && \
  nvm use default

ENV NODE_PATH $NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH $NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

# RUN pyenv update && \
#   pyenv install 3.10.2 && \
#   pyenv global 3.10.2 && \
#   curl -sSL https://install.python-poetry.org | python - && \
#   poetry config virtualenvs.in-project true

FROM gitpod/workspace-full

RUN pyenv update && \
  pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python -

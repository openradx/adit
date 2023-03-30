FROM gitpod/workspace-full

RUN apt-get install -y dcmtk libdcmtk-dev

RUN pyenv update && \
  pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python - && \
  poetry config virtualenvs.in-project true

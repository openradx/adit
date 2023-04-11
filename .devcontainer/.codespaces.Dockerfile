FROM mcr.microsoft.com/devcontainers/universal:latest

RUN pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python - && \
  poetry config virtualenvs.in-project true

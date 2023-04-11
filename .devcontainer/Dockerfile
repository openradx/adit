FROM mcr.microsoft.com/devcontainers/universal

USER codespace

ENV HOME  /home/codespace
ENV PYENV_ROOT="$HOME/.pyenv"
ENV PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"

RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv

RUN pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python - && \
  poetry config virtualenvs.in-project true

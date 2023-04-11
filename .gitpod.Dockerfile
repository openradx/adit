FROM gitpod/workspace-full

USER vscode

RUN curl https://pyenv.run | bash && \

ENV PYENV_ROOT="${HOME}/.pyenv"
ENV PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${PATH}"

RUN pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python - && \
  poetry config virtualenvs.in-project true

FROM gitpod/workspace-postgres

RUN sudo apt update \
    && sudo apt install -y p7zip-full \
    && sudo apt install -y redis-server \
    && pip install --upgrade pip \
    && pip install pipenv \
    && pip install supervisor \
    && sudo rm -rf /var/lib/apt/lists/*
ENV DATABASE_URL psql://gitpod@127.0.0.1:5432/adit
ENV DJANGO_SETTINGS_MODULE adit.settings.development

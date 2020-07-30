FROM gitpod/workspace-postgres

RUN sudo apt-get update \
    && sudo apt-get install -y redis-server \
    && sudo apt-get install -y p7zip-full \
    && pip install --upgrade pip \
    && pip install supervisor \
    && mkdir /tmp/adit_cache_folder \
    && mkdir /tmp/adit_download_folder \
    && sudo rm -rf /var/lib/apt/lists/*
ENV ADIT_AE_TITLE ADIT
ENV ADIT_CACHE_FOLDER /tmp/adit_cache_folder
ENV ADMIN_EMAIL support@adit.test
ENV ADMIN_NAME ADIT Support
ENV DATABASE_URL psql://gitpod@127.0.0.1:5432/adit
ENV DJANGO_SETTINGS_MODULE adit.settings.development
ENV REDIS_URL redis://localhost:6379/0
ENV SQLITE_URL sqlite:///tmp/adit-sqlite.db

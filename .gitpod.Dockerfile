FROM gitpod/workspace-postgres

RUN sudo apt update \
    # playwright dependencies
    && sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libxcb-dri3-0 libcups2 libdrm2 libgbm1 libatspi2.0-0 libgtk-3-0 ffmpeg \
    # 7zip for archiving DICOM files
    && sudo apt install -y p7zip-full \
    # Redis for Celery and LRU cache
    && sudo apt install -y redis-server \
    && pip install --upgrade pip \
    && pip install pipenv \
    && pip install supervisor \
    && sudo rm -rf /var/lib/apt/lists/*
ENV DATABASE_URL psql://gitpod@127.0.0.1:5432/adit
ENV DJANGO_SETTINGS_MODULE adit.settings.development

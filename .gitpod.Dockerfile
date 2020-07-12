FROM gitpod/workspace-postgres

RUN sudo apt-get update \
    && sudo apt-get install -y redis-server \
    && pip install supervisor \
    && mkdir /tmp/adit_cache_folder \
    && mkdir /tmp/adit_download_folder \
    && sudo rm -rf /var/lib/apt/lists/*
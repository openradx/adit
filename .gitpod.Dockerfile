FROM gitpod/workspace-postgres

RUN sudo apt-get update \
    && sudo apt-get install -y redis-server \
    && pip install supervisor \
    && mkdir /tmp/adit_dicom_folder \
    && sudo rm -rf /var/lib/apt/lists/*
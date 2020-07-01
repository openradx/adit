FROM gitpod/workspace-postgres

RUN sudo apt-get update \
    && mkdir /tmp/adit_dicom_folder \
    && sudo apt-get install -y redis-server \
    && sudo apt-get install -y orthanc \
    && pip install supervisor \
    && sudo rm -rf /var/lib/apt/lists/*
FROM gitpod/workspace-full

RUN pyenv update && \
  pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python - && \
  poetry config virtualenvs.in-project true

WORKDIR /usr/src/dcmtk

RUN apt-get -y install libsndfile1-dev libwrap0-dev libopenjp2-7-dev doxygen

RUN wget https://github.com/DCMTK/dcmtk/archive/refs/tags/DCMTK-3.6.7.tar.gz \
  && tar xf DCMTK-3.6.7.tar.gz \
  && mv dcmtk-DCMTK-3.6.7 dcmtk-3.6.7 \
  && mkdir dcmtk-3.6.7-build \
  && cd dcmtk-3.6.7-build \
  && cmake ../dcmtk-3.6.7 \
  && make -j8 \
  && make DESTDIR=../dcmtk-3.6.7-install install \
  && cp -r ..dcmtk-3.6.7-install/usr/local/* /usr/local/
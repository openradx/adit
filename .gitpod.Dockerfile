FROM gitpod/workspace-full

# Python stuff

RUN pyenv install 3.10.2 && \
  pyenv global 3.10.2 && \
  curl -sSL https://install.python-poetry.org | python - && \
  poetry config virtualenvs.in-project true

# Stuff to build and install DCMTK

WORKDIR /usr/src/dcmtk

RUN apt-get update \
  && apt-get -y install cmake libtiff-dev libsndfile1-dev libwrap0-dev libopenjp2-7-dev doxygen \
  && wget https://github.com/DCMTK/dcmtk/archive/refs/tags/DCMTK-3.6.7.tar.gz \
  && tar xvzf DCMTK-3.6.7.tar.gz \
  && mv dcmtk-DCMTK-3.6.7 dcmtk-3.6.7 \
  && mkdir dcmtk-3.6.7-build \
  && cd dcmtk-3.6.7-build \
  && cmake ../dcmtk-3.6.7 -DBUILD_SHARED_LIBS=1 \
  && make -j4 \
  && make DESTDIR=../dcmtk-3.6.7-install install \
  && cp -r ../dcmtk-3.6.7-install/usr/local/* /usr/local/ \
  && ldconfig

# C++ dependencies for dcmcore

RUN apt-get -y install libboost-all-dev catch

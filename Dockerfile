FROM python:3 as base
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apt-get update \
    && apt-get install -y p7zip-full \
    && pip install --upgrade pip \
    && pip install pipenv \
    && mkdir -p /var/www/adit/static \
    && mkdir -p /var/www/adit/ssl \
    && mkdir -p /var/www/adit/logs \
    && mkdir -p /src
COPY ./Pipfile* /src/
WORKDIR /src

FROM base as development
RUN pipenv install --dev --system --deploy --ignore-pipfile
COPY . /src/

FROM base as production
RUN pipenv install --system --deploy --ignore-pipfile
COPY . /src/

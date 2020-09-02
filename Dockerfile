FROM python:3 as base
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apt update \
    && apt install -y p7zip-full \
    && pip install --upgrade pip \
    && pip install pipenv \
    && mkdir -p /var/www/adit/static \
    && mkdir -p /var/www/adit/ssl \
    && mkdir /src
COPY . /src/
WORKDIR /src

FROM base as development
RUN pipenv install --dev --system --deploy --ignore-pipfile

FROM base as production
RUN pipenv install --system --deploy --ignore-pipfile
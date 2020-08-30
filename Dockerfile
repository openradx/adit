FROM python:3 as base
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN pip install --upgrade pip
RUN pip install pipenv
RUN mkdir -p /var/www/adit/static
RUN mkdir -p /var/www/adit/ssl
RUN mkdir /src
COPY . /src/
WORKDIR /src

FROM base as development
RUN pipenv install --dev --system --deploy --ignore-pipfile

FROM base as production
RUN pipenv install --system --deploy --ignore-pipfile
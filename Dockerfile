# Ideas from https://docs.astral.sh/uv/guides/integration/docker/

FROM python:3.12-bullseye AS builder-base

ARG PROJECT_VERSION

# Install dependencies for the `psql` command and 7zip.
# Must match the version of the postgres service in the compose file!
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
  postgresql-common \
  && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
  && apt-get install --no-install-recommends -y \
  postgresql-client-17 \
  p7zip-full \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.6.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# There is no git during image build so we need to provide a fake version
ENV UV_DYNAMIC_VERSIONING_BYPASS=0.0.0

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app


# development image
FROM builder-base AS development

RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-group client

RUN playwright install --with-deps chromium

ADD . /app

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen

ENV PROJECT_VERSION=${PROJECT_VERSION}


# production image
FROM builder-base AS production

RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev --no-group client

ADD . /app

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev --no-group client

ENV PROJECT_VERSION=${PROJECT_VERSION}

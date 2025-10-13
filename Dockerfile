FROM python:3.11-slim

# ===== Environment =====
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
ENV ALEMBIC_CONFIG=/usr/src/alembic.ini

# ===== System deps =====
RUN apt update && apt install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    postgresql-client \
    dos2unix \
    && apt clean

# ===== Poetry install =====
RUN python -m pip install --upgrade pip && \
    pip install poetry

# ===== Copy dependency files =====
COPY ./poetry.lock /usr/src/poetry.lock
COPY ./pyproject.toml /usr/src/pyproject.toml
COPY ./alembic.ini /usr/src/alembic.ini

# ===== Poetry config =====
RUN poetry config virtualenvs.create false

WORKDIR /usr/src
RUN poetry lock
RUN poetry install --no-root --only main

# ===== Copy project =====
COPY ./src ./src
COPY ./commands /commands

# ===== Normalize scripts =====
RUN dos2unix /commands/*.sh
RUN chmod +x /commands/*.sh

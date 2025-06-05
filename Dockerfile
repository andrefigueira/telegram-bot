FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install Poetry and build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-interaction --no-ansi \
    && apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* ~/.cache/pip

COPY . .

# Run as non-root user for security
RUN useradd --create-home bot && chown -R bot:bot /app
USER bot

CMD ["python", "-m", "bot.main"]

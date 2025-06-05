PYTHON=python3.12
VENV=.venv

setup:
pyenv install -s 3.12.1
pyenv virtualenv -f 3.12.1 $(VENV)
$(VENV)/bin/pip install poetry
$(VENV)/bin/poetry install

run:
$(VENV)/bin/poetry run python -m bot.main

lint:
$(VENV)/bin/poetry run ruff bot tests
$(VENV)/bin/poetry run mypy bot

test:
$(VENV)/bin/poetry run pytest --cov=bot --cov-branch --cov-fail-under=100

build:
docker build -t telegram-bot .

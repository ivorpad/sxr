default: check

check: lint konpy test

lint:
    uv run ruff format --check .
    uv run ruff check .

fmt:
    uv run ruff format .
    uv run ruff check --fix .

konpy:
    uv run konpy validate
    uv run konpy check

test:
    uv run pytest

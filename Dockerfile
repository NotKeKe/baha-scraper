FROM python:3.14.2-alpine

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "main.py"]
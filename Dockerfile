FROM python:3.14.2-alpine

WORKDIR /app

# set timezone
RUN apk add --no-cache tzdata \
    && cp /usr/share/zoneinfo/Asia/Taipei /etc/localtime \
    && echo "Asia/Taipei" > /etc/timezone

COPY pyproject.toml uv.lock* ./

RUN pip install --no-cache-dir uv \
    && uv sync --no-dev

COPY . .

CMD ["uv", "run", "main.py"]
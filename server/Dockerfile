FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.13.7

WORKDIR /app
COPY pyproject.toml uv.lock ./
# 开发镜像带上测试和检查工具；生产镜像构建时传 --build-arg UV_SYNC_ARGS=--no-dev
ARG UV_SYNC_ARGS=""
RUN uv sync --frozen $UV_SYNC_ARGS

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

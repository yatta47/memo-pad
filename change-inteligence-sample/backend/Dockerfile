FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
RUN python - <<'PY'
import tomllib, subprocess, sys
with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
deps = data["project"]["dependencies"] + data["project"].get("optional-dependencies", {}).get("dev", [])
subprocess.check_call([sys.executable, "-m", "pip", "install", *deps])
PY

COPY app ./app
COPY tests ./tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

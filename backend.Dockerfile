# backend.Dockerfile
FROM python:3.10-slim

# Prevent Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Install system dependencies (curl is needed to install Poetry)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency definition files first (Better Docker caching)
COPY pyproject.toml poetry.lock ./

# Install python dependencies (no dev tools, no interaction)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy the actual application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Command to run the app


CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
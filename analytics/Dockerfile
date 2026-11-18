FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "elementary-data[dbt1-postgres]==0.26.1" fastapi uvicorn requests
WORKDIR /app
COPY dbt_project.yml packages.yml profiles.yml ./
RUN dbt deps
COPY . .
ENV DBT_PROFILES_DIR=/app DBT_PROJECT_DIR=/app
EXPOSE 4021
CMD ["python", "entrypoint.py"]

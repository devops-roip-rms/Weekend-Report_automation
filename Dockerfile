# Final Weekend Report application image.
# The runtime base contains Python, runtime dependencies, CA certificates, and
# openssh-client. GitLab overrides this ARG with the internal-registry image.
ARG RUNTIME_BASE_IMAGE=weekend-report-runtime-base:python314
FROM ${RUNTIME_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system weekend \
    && useradd \
        --system \
        --gid weekend \
        --home /app \
        weekend

COPY app /app/app
COPY scripts/migrate.py /app/scripts/migrate.py
COPY scripts/database/database_sync_check.ps1 /app/scripts/database/database_sync_check.ps1

RUN mkdir -p /app/runs /app/data /app/config \
    && chown -R weekend:weekend /app

USER weekend

EXPOSE 8080

CMD ["uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "8080"]

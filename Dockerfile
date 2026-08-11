FROM python:3.11-slim@sha256:9e1912aab0a30bbd9488eb79063f68f42a68ab09421595e3062a12c0b3cb8415

ENV PYTHONDONTWRITEBYTECODE=1         PYTHONUNBUFFERED=1         PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system weekend && useradd --system --gid weekend --home /app weekend

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN mkdir -p /app/runs /app/data && chown -R weekend:weekend /app

USER weekend

EXPOSE 8080
CMD ["uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "8080"]

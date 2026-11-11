# The application needs nothing but Python. The image stays small because
# there is nothing to install.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data

WORKDIR /app

# Only installed when you actually want PostgreSQL.
COPY requirements.txt .
ARG WITH_POSTGRES=0
RUN if [ "${WITH_POSTGRES:-0}" = "1" ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

RUN useradd --create-home --uid 10001 agent \
    && mkdir -p /data/resumes && chown -R agent:agent /data /app
USER agent

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=4).status==200 else 1)"

CMD ["python", "run.py", "serve", "--host", "0.0.0.0", "--port", "8080"]

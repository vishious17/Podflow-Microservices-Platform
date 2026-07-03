FROM python:3.11-slim

WORKDIR /app

# curl for healthcheck, no extra bloat
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY honeypot.py .

# requests for geolocation, prometheus-client for metrics, flask for HTTP
RUN pip install --no-cache-dir flask prometheus-client requests

# SQLite data volume mount point
RUN mkdir -p /data

EXPOSE 2222 8888

CMD ["python", "honeypot.py"]

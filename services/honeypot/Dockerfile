FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*
COPY honeypot.py .
RUN pip install --no-cache-dir flask prometheus-client requests
RUN mkdir -p /data
EXPOSE 2222 8888
CMD ["python", "honeypot.py"]

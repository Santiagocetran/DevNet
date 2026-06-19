FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /opt/din

RUN python -m pip install --upgrade pip

COPY pyproject.toml README.md MANIFEST.in ./
COPY dincli ./dincli

RUN pip install --no-cache-dir -e .

COPY dincli/docker/client-worker/client_worker.py /usr/local/bin/din-client-worker
RUN chmod +x /usr/local/bin/din-client-worker

WORKDIR /din

ENTRYPOINT ["din-client-worker"]

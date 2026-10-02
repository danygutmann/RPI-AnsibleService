FROM python:3.12-slim

ENV APP_DIR=/app \
    ANSIBLE_COLLECTIONS_PATH=/app/collections \
    ANSIBLE_LOG_PATH=/tmp/ansible.log \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    git \
    && pip install --no-cache-dir flask ansible-core \
    && rm -rf /var/lib/apt/lists/*

RUN ansible-galaxy collection install -p /app/collections community.docker community.general

COPY . /app

EXPOSE 5000

CMD ["python", "/app/app.py"]

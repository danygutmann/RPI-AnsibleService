FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    git \
    && pip install --no-cache-dir flask ansible-core \
    && rm -rf /var/lib/apt/lists/*

COPY app.py /app/app.py

CMD ["python", "/app/app.py"]
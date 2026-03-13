FROM python:3.12-slim-bookworm

# System deps + Gitleaks binary (pinned) + non-root user — single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl gcc git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSfL --retry 3 --retry-delay 5 \
       https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz \
       -o /tmp/gitleaks.tar.gz \
    && echo "5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba  /tmp/gitleaks.tar.gz" | sha256sum -c - \
    && tar -xz -C /usr/local/bin gitleaks -f /tmp/gitleaks.tar.gz \
    && rm /tmp/gitleaks.tar.gz \
    && useradd -m -s /bin/bash vscode
USER vscode

ENV PATH=/home/vscode/.local/bin:$PATH

WORKDIR /workspace

CMD ["sleep", "infinity"]

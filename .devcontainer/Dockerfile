FROM python:3.12-slim-bookworm

# System deps — single layer, clean up apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

# Gitleaks binary (pinned version)
RUN curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz \
    | tar -xz -C /usr/local/bin gitleaks

# Non-root user
RUN useradd -m -s /bin/bash vscode
USER vscode

WORKDIR /workspace

CMD ["sleep", "infinity"]

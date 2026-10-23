FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*
ENV NVM_DIR=/root/.nvm
RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" && nvm install 22 && nvm alias default 22 \
    && npm i -g opencode-ai \
    && ln -sf "$(dirname "$(nvm which 22)")"/node /usr/local/bin/node \
    && ln -sf "$(dirname "$(nvm which 22)")"/npm /usr/local/bin/npm \
    && ln -sf "$(dirname "$(nvm which 22)")"/opencode /usr/local/bin/opencode
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash

WORKDIR /app
COPY case /app/case
RUN mkdir -p /app/outputs /app/answers /logs/verifier

CMD ["bash"]

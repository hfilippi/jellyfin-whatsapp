FROM python:3.12-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_ROOT_USER_ACTION=ignore
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV CHROME_BIN=/usr/bin/chromium-shell
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y curl wget gnupg supervisor chromium-shell chromium-driver fonts-liberation libatk-bridge2.0-0t64 libgtk-3-0t64 libnss3 libxss1 libasound2t64 xdg-utils ca-certificates nodejs npm && rm -rf /var/lib/apt/lists/*

# Install Node.js dependencies
COPY package.json package-lock.json* ./
RUN npm install
COPY server.js ./

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Container setup
COPY . .
RUN mkdir -p /data/session

ARG APP_VERSION=0.0.0

LABEL org.opencontainers.image.title="jellyfin-whatsapp"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="A notification system that sends messages to WhatsApp when new media is added to Jellyfin."
LABEL maintainer="hfilippi"

ENV APP_VERSION=${APP_VERSION}

EXPOSE 8000
EXPOSE 3000

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
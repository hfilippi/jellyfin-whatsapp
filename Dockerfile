FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y curl wget gnupg supervisor chromium-shell chromium-driver fonts-liberation libatk-bridge2.0-0t64 libgtk-3-0t64 libnss3 libxss1 libasound2t64 xdg-utils ca-certificates nodejs npm && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm install

COPY server.js ./

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/session

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV CHROME_BIN=/usr/bin/chromium-shell

EXPOSE 8000
EXPOSE 3000

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# FFmpeg for Discord voice playback + Node 22 for yt-dlp EJS and
# the bgutil Proof-of-Origin token provider.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl git gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && node --version \
    && npm --version \
    && rm -rf /var/lib/apt/lists/*

# Build the local bgutil POT provider. It lets yt-dlp obtain YouTube
# Proof-of-Origin tokens automatically; no browser cookies are required.
RUN git clone --depth 1 --branch 1.3.1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-ytdlp-pot-provider \
    && cd /opt/bgutil-ytdlp-pot-provider/server \
    && npm ci --no-audit --no-fund \
    && npx tsc

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Start the POT provider and then the Discord bot in the same Railway service.
CMD ["sh", "-c", "node /opt/bgutil-ytdlp-pot-provider/server/build/main.js --port 4416 >/tmp/bgutil-pot.log 2>&1 & exec python main.py"]

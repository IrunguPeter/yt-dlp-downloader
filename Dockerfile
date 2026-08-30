FROM python:3.12-slim

WORKDIR /app

# System deps for ffmpeg (video/audio merging) and yt-dlp runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY download_media.py .

# Work in a fast writable temp dir for partial downloads when run via compose
ENV HOME=/tmp \
    PYTHONUNBUFFERED=1

# yt-dlp is invoked via our script. Entrypoint forwards all args to the script.
ENTRYPOINT ["python", "download_media.py"]

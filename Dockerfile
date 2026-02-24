FROM python:3.11-slim

# Install FFmpeg and curl (needed for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Setup app
WORKDIR /app
COPY app.py .
# Optional: COPY .streamlit .streamlit (Uncomment if you have a .streamlit/config.toml)

# Create notebooklm home
RUN mkdir -p /tmp/notebooklm

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
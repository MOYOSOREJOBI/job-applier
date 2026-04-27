FROM python:3.11-slim

# System deps for WeasyPrint + Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libglib2.0-0 \
    shared-mime-info \
    fonts-liberation \
    ttf-mscorefonts-installer \
    wget \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Playwright browser deps
RUN pip install playwright && playwright install chromium --with-deps 2>/dev/null || true

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create runtime dirs
RUN mkdir -p artifacts logs storage config

ENV PORT=7700
EXPOSE 7700

CMD ["python", "-m", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "7700"]

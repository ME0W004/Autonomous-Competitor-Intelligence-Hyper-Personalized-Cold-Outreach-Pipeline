FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for Playwright & Crawl4AI
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    wget \
    gnupg \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser dependencies
RUN playwright install --with-deps chromium

# Copy codebase
COPY . /app/

ENTRYPOINT ["python", "src/cli.py"]
CMD ["run", "--help"]

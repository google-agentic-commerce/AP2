# Multi-stage Dockerfile for AI Shopping Concierge
# Optimized for production deployment

# Build stage
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Add metadata labels
LABEL org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.url="https://github.com/your-username/ai-shopping-concierge-ap2" \
      org.opencontainers.image.source="https://github.com/your-username/ai-shopping-concierge-ap2" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.vendor="AI Shopping Concierge" \
      org.opencontainers.image.title="AI Shopping Concierge" \
      org.opencontainers.image.description="Intelligent shopping assistant built on AP2 protocol"

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create and use non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app"

# Set work directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .

# Initialize AP2 submodule if needed
RUN if [ -d ".git" ]; then \
        git submodule update --init --recursive; \
    fi

# Create necessary directories
RUN mkdir -p logs config && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create health check script
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/health || exit 1' > /app/healthcheck.sh && \
    chmod +x /app/healthcheck.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD /app/healthcheck.sh

# Default command
CMD ["python", "-m", "ai_shopping_agent"]

# Development stage (optional)
FROM production as development

USER root

# Install development dependencies
RUN pip install pytest pytest-asyncio pytest-cov black isort mypy

# Install debugging tools
RUN apt-get update && apt-get install -y \
    vim \
    htop \
    && rm -rf /var/lib/apt/lists/*

USER appuser

# Override command for development
CMD ["python", "-m", "ai_shopping_agent", "--reload"]
ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and build deps
RUN apk add --no-cache \
        python3 \
        py3-pip \
        py3-yaml \
        curl \
        jq \
        gcc \
        musl-dev \
        python3-dev \
        libffi-dev \
        openssl-dev

# Install Python packages
RUN pip3 install --no-cache-dir --break-system-packages \
        fastapi \
        "uvicorn[standard]" \
        httpx \
        openai \
        google-genai \
        anthropic \
        websockets \
        pyyaml \
        aiofiles

# Cleanup build deps
RUN apk del gcc musl-dev python3-dev libffi-dev openssl-dev

# Copy application
COPY app/ /app/

# Copy startup script
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app

# Override the base image's s6-overlay entrypoint
ENTRYPOINT []
CMD ["/run.sh"]

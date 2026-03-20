ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python 3 and build dependencies
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

# Cleanup build deps to save space
RUN apk del gcc musl-dev python3-dev libffi-dev openssl-dev

# Copy application
COPY app/ /app/

# Copy s6-overlay service definition
COPY rootfs /

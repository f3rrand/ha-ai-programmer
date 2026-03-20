ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and pip
RUN apk add --no-cache \
        python3 \
        py3-pip \
        py3-yaml \
        gcc \
        musl-dev \
        python3-dev \
        libffi-dev \
        openssl-dev \
    && pip3 install --no-cache-dir --break-system-packages \
        fastapi \
        "uvicorn[standard]" \
        httpx \
        openai \
        google-genai \
        anthropic \
        websockets \
        pyyaml \
        aiofiles \
    && apk del gcc musl-dev python3-dev libffi-dev openssl-dev

# Copy application
COPY app/ /app/

# Copy s6-overlay service definitions
COPY rootfs /

# Ensure run script is executable
RUN chmod a+x /etc/s6-overlay/s6-rc.d/ai-programmer/run

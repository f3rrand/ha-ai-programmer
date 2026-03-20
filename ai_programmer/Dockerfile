ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system deps and Python packages
RUN apk add --no-cache \
        curl \
        jq \
    && pip3 install --no-cache-dir --break-system-packages \
        fastapi \
        uvicorn[standard] \
        httpx \
        openai \
        google-genai \
        anthropic \
        websockets \
        pyyaml \
        aiofiles

# Copy application
COPY app/ /app/

WORKDIR /app

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]

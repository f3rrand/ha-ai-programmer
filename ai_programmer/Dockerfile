ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache curl jq bash gcc musl-dev libffi-dev openssl-dev

RUN pip install --no-cache-dir \
        fastapi \
        "uvicorn[standard]" \
        httpx \
        openai \
        google-genai \
        anthropic \
        websockets \
        pyyaml \
        aiofiles

RUN apk del gcc musl-dev libffi-dev openssl-dev

COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app

ENTRYPOINT []
CMD ["/run.sh"]

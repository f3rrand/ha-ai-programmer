#!/usr/bin/with-contenv bashio
# HA AI Programmer — startup script

bashio::log.info "=== AI Programmer starting ==="

# Read config from HA add-on options (with safe defaults for optional values)
export AI_PROVIDER=$(bashio::config 'ai_provider' 'gemini')

if bashio::config.has_value 'gemini_api_key'; then
    export GEMINI_API_KEY=$(bashio::config 'gemini_api_key')
else
    export GEMINI_API_KEY=""
fi

if bashio::config.has_value 'gemini_model'; then
    export GEMINI_MODEL=$(bashio::config 'gemini_model')
else
    export GEMINI_MODEL="gemini-2.5-flash"
fi

if bashio::config.has_value 'openai_api_key'; then
    export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
else
    export OPENAI_API_KEY=""
fi

if bashio::config.has_value 'openai_model'; then
    export OPENAI_MODEL=$(bashio::config 'openai_model')
else
    export OPENAI_MODEL="gpt-4o"
fi

if bashio::config.has_value 'anthropic_api_key'; then
    export ANTHROPIC_API_KEY=$(bashio::config 'anthropic_api_key')
else
    export ANTHROPIC_API_KEY=""
fi

if bashio::config.has_value 'anthropic_model'; then
    export ANTHROPIC_MODEL=$(bashio::config 'anthropic_model')
else
    export ANTHROPIC_MODEL="claude-sonnet-4-20250514"
fi

if bashio::config.has_value 'ollama_url'; then
    export OLLAMA_URL=$(bashio::config 'ollama_url')
else
    export OLLAMA_URL=""
fi

if bashio::config.has_value 'ollama_model'; then
    export OLLAMA_MODEL=$(bashio::config 'ollama_model')
else
    export OLLAMA_MODEL="llama3.1"
fi

# HA Supervisor token is auto-injected
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"

# HA config directory (mapped via config.yaml)
export HA_CONFIG_DIR="/config"

# Ingress
export INGRESS_PATH=$(bashio::addon.ingress_entry)

bashio::log.info "Provider: ${AI_PROVIDER}"
bashio::log.info "Ingress path: ${INGRESS_PATH}"
bashio::log.info "HA URL: ${HA_URL}"
bashio::log.info "Config dir: ${HA_CONFIG_DIR}"

# Check Python
bashio::log.info "Python version: $(python3 --version 2>&1)"

# Start the server
bashio::log.info "Starting uvicorn on port 8099..."
cd /app
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8099

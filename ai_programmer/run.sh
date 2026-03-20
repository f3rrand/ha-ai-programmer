#!/usr/bin/with-contenv bashio
# HA AI Programmer — startup script

# Read config from HA add-on options
export AI_PROVIDER=$(bashio::config 'ai_provider')
export GEMINI_API_KEY=$(bashio::config 'gemini_api_key')
export GEMINI_MODEL=$(bashio::config 'gemini_model')
export OPENAI_API_KEY=$(bashio::config 'openai_api_key')
export OPENAI_MODEL=$(bashio::config 'openai_model')
export ANTHROPIC_API_KEY=$(bashio::config 'anthropic_api_key')
export ANTHROPIC_MODEL=$(bashio::config 'anthropic_model')
export OLLAMA_URL=$(bashio::config 'ollama_url')
export OLLAMA_MODEL=$(bashio::config 'ollama_model')

# HA Supervisor token is auto-injected
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"

# HA config directory (mapped via config.yaml)
export HA_CONFIG_DIR="/config"

# Ingress
export INGRESS_PATH=$(bashio::addon.ingress_entry)

bashio::log.info "Starting AI Programmer..."
bashio::log.info "Provider: ${AI_PROVIDER}"
bashio::log.info "Ingress: ${INGRESS_PATH}"

cd /app
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8099

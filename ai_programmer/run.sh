#!/bin/bash
# HA AI Programmer — startup script (init: false mode, no s6/bashio)

echo "=== AI Programmer starting ==="

# Read add-on options from the HA options file
OPTIONS_FILE="/data/options.json"

if [ -f "$OPTIONS_FILE" ]; then
    echo "Reading config from $OPTIONS_FILE"
    export AI_PROVIDER=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('ai_provider','gemini'))")
    export GEMINI_API_KEY=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('gemini_api_key',''))")
    export GEMINI_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('gemini_model','gemini-2.5-flash'))")
    export OPENAI_API_KEY=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('openai_api_key',''))")
    export OPENAI_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('openai_model','gpt-4o'))")
    export ANTHROPIC_API_KEY=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('anthropic_api_key',''))")
    export ANTHROPIC_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('anthropic_model','claude-sonnet-4-20250514'))")
    export OLLAMA_URL=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('ollama_url',''))")
    export OLLAMA_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS_FILE')).get('ollama_model','llama3.1'))")
else
    echo "No options file found, using env defaults"
fi

# HA Supervisor token is auto-injected as env var
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"
export HA_CONFIG_DIR="/config"

echo "Provider: ${AI_PROVIDER}"
echo "HA URL: ${HA_URL}"
echo "Config dir: ${HA_CONFIG_DIR}"
echo "Python: $(python3 --version 2>&1)"

# Start the server
echo "Starting uvicorn on port 8099..."
cd /app
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8099

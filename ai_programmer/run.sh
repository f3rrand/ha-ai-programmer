#!/bin/bash
# HA AI Programmer — startup script (no s6, no bashio)

echo "=== AI Programmer starting ==="

OPTIONS="/data/options.json"

if [ -f "$OPTIONS" ]; then
    echo "Reading config from $OPTIONS"
    export AI_PROVIDER=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('ai_provider','gemini'))")
    export GEMINI_API_KEY=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('gemini_api_key',''))")
    export GEMINI_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('gemini_model','gemini-2.5-flash'))")
    export OPENAI_API_KEY=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('openai_api_key',''))")
    export OPENAI_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('openai_model','gpt-4o'))")
    export ANTHROPIC_API_KEY=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('anthropic_api_key',''))")
    export ANTHROPIC_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('anthropic_model','claude-sonnet-4-6-20250627'))")
    export OLLAMA_URL=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('ollama_url',''))")
    export OLLAMA_MODEL=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('ollama_model','llama3.1'))")
else
    echo "WARNING: No options file found at $OPTIONS"
fi

export HA_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"
export HA_CONFIG_DIR="/config"

echo "Provider: ${AI_PROVIDER}"
echo "HA URL: ${HA_URL}"
echo "Python: $(python3 --version 2>&1)"

echo "Starting uvicorn on port 8099..."
cd /app
exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8099

# HA AI Programmer — Project Guide

## Project Overview

This is a Home Assistant add-on / standalone Docker app that provides a natural-language AI chat interface for programming and controlling Home Assistant. It supports multiple AI providers (Gemini, OpenAI, Anthropic, Ollama) switchable at runtime, and exposes 25 tools that give the AI full control over a HA instance.

**Repo:** https://github.com/f3rrand/ha-ai-programmer
**Owner:** Stanley Ferrand (f3rrand)

## Repository Structure

```
ha-addon-repo/
├── repository.yaml              # HA add-on repo manifest (name, URL, maintainer)
├── README.md                    # User-facing install & usage docs
├── CLAUDE.md                    # This file — project context for AI assistants
└── ai_programmer/               # The add-on itself
    ├── config.yaml              # HA add-on manifest (arch, ingress, options schema)
    ├── build.yaml               # Base Docker images per architecture
    ├── Dockerfile               # Alpine + Python 3.11, installs pip deps
    ├── run.sh                   # Entrypoint: reads bashio config, exports env vars, starts uvicorn
    ├── icon.png                 # 256x256 add-on icon
    ├── logo.png                 # 128x128 add-on logo
    ├── CHANGELOG.md
    └── app/
        ├── app.py               # FastAPI backend — ALL server logic in one file (~957 lines)
        └── static/
            └── index.html       # Chat UI — single-file HTML/CSS/JS (~600+ lines)
```

## Architecture

### Backend (app.py)

Single-file FastAPI application. No ORM, no database — all state is in-memory.

**Key sections (in order):**

1. **Config (lines 19-34):** All settings from env vars with defaults. `AI_PROVIDER`, API keys for 4 providers, `HA_TOKEN`, `HA_URL`, `HA_CONFIG_DIR`, `INGRESS_PATH`.

2. **HA HTTP Client (lines 39-70):** Async httpx client with helpers:
   - `ha_get(path)` / `ha_post(path, body)` — talk to HA Core REST API
   - `supervisor_get(path)` / `supervisor_post(path, body)` — talk to HA Supervisor API (only works when running as add-on)
   - Auth via Bearer token in headers

3. **Tool Definitions (lines 77-384):** `HA_TOOLS` list — 25 tools as dicts with `name`, `description`, `parameters` (JSON Schema). Organized into categories:
   - **Entity & State:** `ha_get_entities`, `ha_get_entity_state`, `ha_call_service`
   - **YAML File Ops:** `ha_read_file`, `ha_write_file`, `ha_list_files`, `ha_append_to_yaml`
   - **Automation:** `ha_create_automation`
   - **Blueprints:** `ha_create_blueprint`, `ha_list_blueprints`
   - **Dashboards:** `ha_get_dashboards`, `ha_get_dashboard_config`, `ha_update_dashboard`
   - **HACS:** `ha_hacs_list_repos`, `ha_hacs_install`, `ha_hacs_search`
   - **System:** `ha_render_template`, `ha_get_history`, `ha_get_error_log`, `ha_check_config`, `ha_reload`, `ha_restart`, `ha_get_addons`, `ha_get_system_info`, `ha_install_custom_component`

4. **Tool Execution (lines 391-665):** `execute_tool(name, inp)` — giant if/elif dispatcher. Each tool is self-contained. File operations use `pathlib.Path`, YAML ops use `pyyaml`. File writes auto-backup to `.bak`. HACS reads from `.storage/hacs.repositories` JSON file. Custom component installer downloads from GitHub API.

5. **Tool Format Converters (lines 672-679):** Three functions that convert the universal `HA_TOOLS` format to provider-specific formats:
   - `tools_for_openai()` — wraps in `{"type": "function", "function": {...}}`
   - `tools_for_gemini()` — wraps in `{"function_declarations": [...]}`
   - `tools_for_anthropic()` — renames `parameters` to `input_schema`

6. **System Prompt (lines 686-711):** Injected into every AI call. Instructs the AI to read before editing, check config after writes, use modern HA syntax, etc.

7. **Provider Chat Implementations (lines 720-852):** Four async functions, one per provider. Each implements the tool-use loop:
   - `chat_openai(messages, tool_actions)` — uses `openai` SDK, OpenAI function calling format
   - `chat_gemini(messages, tool_actions)` — uses `google-genai` SDK, Gemini function calling with `types.Part.from_function_response`
   - `chat_anthropic(messages, tool_actions)` — uses `anthropic` SDK, native tool_use blocks
   - `chat_ollama(messages, tool_actions)` — uses `openai` SDK pointed at Ollama's OpenAI-compatible endpoint

   All four follow the same pattern: build provider-specific message history → loop: call API → if tool calls, execute them and append results → if text response, return it.

8. **API Endpoints (lines 859-957):**
   - `POST /api/chat` — main chat endpoint. Takes `{message, session_id}`, dispatches to provider, returns `{response, tool_actions, session_id}`
   - `GET /api/ha-status` — checks HA connectivity
   - `GET /api/provider` — returns current provider, model, key status
   - `POST /api/settings` — hot-swap provider/keys/models at runtime (no restart needed)
   - `GET /api/ha-entities-summary` — entity counts by domain
   - `GET /` — serves index.html

### Frontend (index.html)

Single-file dark-themed chat UI. Pure vanilla JS, no build tools, no frameworks.

**Features:**
- Chat interface with markdown rendering
- Tool action badges on AI messages (shows which HA tools were called)
- Entity sidebar (collapsible, shows domain counts)
- Settings modal with 4 provider cards (OpenAI, Gemini, Anthropic, Ollama)
- HA connection status indicator
- Session management
- Suggestion cards on empty state (blueprint, dashboard, HACS, YAML review)

**CSS variables** defined in `:root` — dark theme colors, accent blue `#4da6ff`.

### Docker / Add-on Setup

**Dockerfile:** Based on HA's architecture-specific Python 3.11 Alpine images (defined in `build.yaml`). Installs: fastapi, uvicorn, httpx, openai, google-genai, anthropic, websockets, pyyaml, aiofiles.

**run.sh:** Uses `bashio` to read add-on config options → exports as env vars. Uses auto-injected `SUPERVISOR_TOKEN` for HA auth. Starts uvicorn on port 8099.

**config.yaml:** Defines add-on metadata. Key settings:
- `ingress: true` + `ingress_port: 8099` — sidebar integration
- `map: config:rw, addons:ro, share:rw, ssl:ro` — filesystem access
- `homeassistant_api: true` — gets Supervisor token
- Options schema: all AI provider settings as optional strings

## How Communication Works

### As HA Add-on (HAOS only)
- App runs inside Docker container managed by HA Supervisor
- `SUPERVISOR_TOKEN` auto-injected — no manual token needed
- Talks to HA via `http://supervisor/core/api/...`
- `/config` directory is bind-mounted for direct file access
- Ingress provides authentication passthrough from HA

### As Standalone Docker Container (HA Core/Container)
- User provides `HA_URL` (e.g., `http://192.168.1.100:8123`) and `HA_TOKEN` (long-lived access token)
- Talks to HA via standard REST API over the network
- `/config` mounted via Docker volume for file operations
- Accessed directly at `http://<host>:8099`
- No Supervisor API available (add-on list, system info fall back to REST API)

### As Local Python App (development)
- Same as standalone but runs via `python3 app.py` or `uvicorn app:app`
- Needs venv with deps: `pip install fastapi uvicorn httpx openai google-genai anthropic pyyaml`
- Set env vars or use `.env` file
- `HA_CONFIG_DIR` can point to any local directory for testing

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `gemini` | Active provider: `gemini`, `openai`, `anthropic`, `ollama` |
| `GEMINI_API_KEY` | `""` | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `OPENAI_API_KEY` | `""` | OpenAI API key (requires paid API access, not ChatGPT Plus) |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model name |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model name |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1` | Ollama model name |
| `HA_TOKEN` | `""` | HA long-lived access token (or auto-injected SUPERVISOR_TOKEN) |
| `HA_URL` | `http://supervisor/core` | HA base URL |
| `HA_CONFIG_DIR` | `/config` | Path to HA config directory |
| `INGRESS_PATH` | `""` | HA ingress base path (set automatically by Supervisor) |

## Key Design Decisions

1. **Single-file backend:** Everything in one `app.py` for simplicity. No models, no services layer, no separate router files. The tool dispatcher is a flat if/elif chain — easy to read, easy to add new tools.

2. **Universal tool format:** Tools defined once in a neutral JSON Schema format, then converted per-provider. Adding a new tool = add to `HA_TOOLS` list + add elif in `execute_tool`.

3. **No database:** Conversations stored in-memory dict keyed by session_id. Trimmed to last 40 messages. Resets on restart. This is intentional — it's a programming tool, not a chat history app.

4. **Auto-backup on write:** Every file write creates a `.bak` copy first. This is critical safety for a tool that edits HA config files.

5. **File operations via filesystem, not API:** YAML editing uses direct file I/O (pathlib + pyyaml) rather than HA's REST API. This gives more power (can edit ANY file) but requires the `/config` mount.

6. **HACS via storage file:** HACS doesn't expose a REST API, so we read its internal `.storage/hacs.repositories` JSON file for search/list, and use the `hacs/install` service call for installs.

## Common Development Tasks

### Adding a new tool
1. Add tool definition dict to `HA_TOOLS` list (name, description, parameters)
2. Add `elif name == "ha_new_tool":` block in `execute_tool()`
3. That's it — format converters and chat implementations pick it up automatically

### Adding a new AI provider
1. Add env vars for key/model at top
2. Add format converter if needed (or reuse OpenAI format)
3. Add `async def chat_newprovider(messages, tool_actions)` function
4. Add to `providers` dict in `chat()` endpoint
5. Add to settings endpoint globals
6. Update frontend settings modal with new provider card

### Testing locally
```bash
cd ha-addon-repo/ai_programmer/app
export AI_PROVIDER=gemini
export GEMINI_API_KEY=your_key
export HA_URL=http://your-ha-ip:8123
export HA_TOKEN=your_long_lived_token
export HA_CONFIG_DIR=/path/to/ha/config
python3 -m uvicorn app:app --host 0.0.0.0 --port 8099 --reload
```

### Building Docker image locally
```bash
cd ha-addon-repo/ai_programmer
docker build --build-arg BUILD_FROM=python:3.11-alpine -t ha-ai-programmer .
docker run --network host \
  -e AI_PROVIDER=gemini \
  -e GEMINI_API_KEY=your_key \
  -e HA_URL=http://localhost:8123 \
  -e HA_TOKEN=your_token \
  -v /path/to/config:/config \
  ha-ai-programmer
```

## Known Limitations & Future Ideas

- **No streaming:** Responses come back all at once. Could add SSE streaming for better UX.
- **No persistent chat history:** Conversations are lost on restart. Could add SQLite or file-based storage.
- **HACS search is local only:** Searches the already-downloaded HACS repo list, not the full HACS store online.
- **No WebSocket support:** Some HA features (like real-time event streams) need WebSocket. Currently REST-only.
- **Single concurrent user:** Conversation dict is global. Multiple users would see each other's history.
- **No auth in standalone mode:** When running outside HA ingress, there's no login page. Anyone on the network can access it.
- **Supervisor tools fail gracefully:** `ha_get_addons` and `ha_get_system_info` catch exceptions and fall back when Supervisor API isn't available (i.e., not running as HAOS add-on).

## Dependencies

Python packages (installed in Dockerfile):
- `fastapi` + `uvicorn` — web server
- `httpx` — async HTTP client for HA API
- `openai` — OpenAI + Ollama (OpenAI-compatible) SDK
- `google-genai` — Google Gemini SDK
- `anthropic` — Anthropic Claude SDK
- `pyyaml` — YAML parsing/writing for HA configs
- `aiofiles` — async file I/O (imported but not heavily used yet)
- `websockets` — dependency for some provider SDKs

## HA Installation Type Note

This repo was designed as an HA add-on (HAOS), but the owner's Pi runs **HA Core/Container** (no Supervisor, no add-on store). The app works as a standalone Docker container with manual `HA_URL` + `HA_TOKEN` configuration. Supervisor-dependent tools (`ha_get_addons`, `ha_get_system_info` via Supervisor) will return fallback data.

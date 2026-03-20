# HA AI Programmer

A Home Assistant add-on that lets you control, configure, and program your entire HA instance through natural language chat.

## Features

- **Multi-provider AI**: Switch between Gemini, OpenAI, Anthropic, or Ollama (local) from the UI
- **25 powerful tools**: Entity control, YAML editing, automations, blueprints, dashboards, HACS management, system diagnostics
- **Sidebar integration**: Appears as a panel in your HA sidebar via ingress
- **Safe file editing**: Automatic backups before any file overwrite
- **HACS support**: Search, install, and manage HACS repositories
- **Blueprint generator**: Create reusable automation templates
- **Dashboard builder**: Read and modify Lovelace dashboards

## Installation

1. In Home Assistant, go to **Settings > Add-ons > Add-on Store**
2. Click the **three dots** menu (top right) > **Repositories**
3. Add this URL: `https://github.com/stanleyferrand/ha-ai-programmer`
4. Click **Add**, then refresh the page
5. Find **AI Programmer** in the store and click **Install**
6. Go to the **Configuration** tab and set your AI provider and API key
7. Start the add-on and click **Open Web UI** (or find it in the sidebar)

## Configuration

| Option | Description |
|--------|-------------|
| `ai_provider` | `gemini`, `openai`, `anthropic`, or `ollama` |
| `gemini_api_key` | Your Google AI Studio API key |
| `gemini_model` | Model name (default: `gemini-2.5-flash`) |
| `openai_api_key` | Your OpenAI API key |
| `openai_model` | Model name (default: `gpt-4o`) |
| `anthropic_api_key` | Your Anthropic API key |
| `anthropic_model` | Model name (default: `claude-sonnet-4-20250514`) |
| `ollama_url` | Ollama server URL (e.g. `http://192.168.1.100:11434`) |
| `ollama_model` | Ollama model name (default: `llama3.1`) |

## What it can do

- "Turn on all the lights in the living room"
- "Create an automation that turns off lights at midnight"
- "Build me a dashboard with temperature sensors and light controls"
- "Search HACS for mushroom cards and install them"
- "Generate a blueprint for a motion-activated light with timeout input"
- "Check my config for errors"
- "Show me the error log"
- "What custom components do I have installed?"

"""
HA AI Programmer — Full-power Home Assistant programmer add-on.
Runs inside HA with direct access to config files, HACS, dashboards, and more.
"""

from __future__ import annotations

import os, json, glob, uuid, httpx, traceback, re, shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import yaml

# ── Config ────────────────────────────────────────────────────────────────────
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL      = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "llama3.1")

HA_TOKEN      = os.getenv("HA_TOKEN", os.getenv("SUPERVISOR_TOKEN", ""))
HA_URL        = os.getenv("HA_URL", "http://supervisor/core")
HA_CONFIG_DIR = os.getenv("HA_CONFIG_DIR", "/config")
INGRESS_PATH  = os.getenv("INGRESS_PATH", "")

app = FastAPI(title="HA AI Programmer")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# ── HA HTTP client ────────────────────────────────────────────────────────────
ha_client = httpx.AsyncClient(timeout=30.0)

def ha_headers():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

async def ha_get(path: str) -> Any:
    r = await ha_client.get(f"{HA_URL}{path}", headers=ha_headers())
    r.raise_for_status()
    return r.json()

async def ha_post(path: str, body: Optional[dict] = None) -> Any:
    r = await ha_client.post(f"{HA_URL}{path}", headers=ha_headers(), json=body or {})
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return r.text

async def supervisor_get(path: str) -> Any:
    """Call the HA Supervisor API."""
    r = await ha_client.get(f"http://supervisor{path}", headers=ha_headers())
    r.raise_for_status()
    return r.json()

async def supervisor_post(path: str, body: Optional[dict] = None) -> Any:
    r = await ha_client.post(f"http://supervisor{path}", headers=ha_headers(), json=body or {})
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return r.text


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS — the AI's full power set
# ══════════════════════════════════════════════════════════════════════════════

HA_TOOLS = [
    # ── Entity & State Tools ──────────────────────────────────────────────────
    {
        "name": "ha_get_entities",
        "description": "List HA entities, optionally filtered by domain (light, switch, sensor, climate, automation, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain to filter by, e.g. 'light', 'sensor'."}
            },
            "required": [],
        },
    },
    {
        "name": "ha_get_entity_state",
        "description": "Get the full state and attributes of a single entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID, e.g. 'light.kitchen'."}
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_call_service",
        "description": "Call a HA service to control devices (light.turn_on, switch.toggle, climate.set_temperature, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Service domain."},
                "service": {"type": "string", "description": "Service name."},
                "service_data": {"type": "object", "description": "Service data including entity_id and parameters."},
            },
            "required": ["domain", "service", "service_data"],
        },
    },

    # ── YAML File Tools ───────────────────────────────────────────────────────
    {
        "name": "ha_read_file",
        "description": (
            "Read any file from the HA config directory. "
            "Use for: configuration.yaml, automations.yaml, scripts.yaml, scenes.yaml, "
            "secrets.yaml, customize.yaml, lovelace dashboards, packages, etc. "
            "Path is relative to /config/."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to config dir, e.g. 'automations.yaml' or 'dashboards/overview.yaml'."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "ha_write_file",
        "description": (
            "Write or overwrite a file in the HA config directory. "
            "Creates parent directories if needed. Use for creating/editing YAML configs, "
            "custom components, scripts, dashboards, blueprints, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to config dir."},
                "content": {"type": "string", "description": "Full file content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "ha_list_files",
        "description": "List files/directories in the HA config directory. Supports glob patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern relative to config dir, e.g. '*.yaml', 'custom_components/*', 'blueprints/**/*.yaml'."}
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "ha_append_to_yaml",
        "description": (
            "Append a YAML block to an existing YAML list file (e.g. add a new automation to automations.yaml, "
            "or a new script to scripts.yaml). Reads the file, parses it, appends the entry, and writes it back."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "YAML file path relative to config dir."},
                "entry": {"type": "object", "description": "The YAML entry to append (as a JSON object that will be converted to YAML)."},
            },
            "required": ["path", "entry"],
        },
    },

    # ── Automation Tools ──────────────────────────────────────────────────────
    {
        "name": "ha_list_automations",
        "description": (
            "List all automations with their full configuration (triggers, conditions, actions). "
            "Returns every automation's ID, alias, state, and config details. "
            "Use this to see what automations already exist before creating or modifying them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "automation_id": {"type": "string", "description": "Optional: get config for a single automation by entity_id (e.g. 'automation.morning_lights')."},
            },
            "required": [],
        },
    },
    {
        "name": "ha_create_automation",
        "description": "Create a new automation via the HA config API (no YAML editing needed).",
        "parameters": {
            "type": "object",
            "properties": {
                "automation_id": {"type": "string", "description": "Unique snake_case ID."},
                "config": {"type": "object", "description": "Full automation config: alias, description, trigger, condition, action, mode."},
            },
            "required": ["automation_id", "config"],
        },
    },

    # ── Blueprint Tools ───────────────────────────────────────────────────────
    {
        "name": "ha_create_blueprint",
        "description": (
            "Create a HA Blueprint YAML file. Blueprints are reusable automation templates "
            "with configurable inputs. Saved to blueprints/automation/ directory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Blueprint filename (without .yaml)."},
                "content": {"type": "string", "description": "Full Blueprint YAML content."},
            },
            "required": ["name", "content"],
        },
    },
    {
        "name": "ha_list_blueprints",
        "description": "List all installed blueprints (both automation and script blueprints).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ── Dashboard / Lovelace Tools ────────────────────────────────────────────
    {
        "name": "ha_get_dashboards",
        "description": "List all Lovelace dashboards.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "ha_get_dashboard_config",
        "description": "Get the full Lovelace config for a dashboard.",
        "parameters": {
            "type": "object",
            "properties": {
                "dashboard_id": {"type": "string", "description": "Dashboard URL path, e.g. 'lovelace' for the default, or a custom dashboard ID."}
            },
            "required": ["dashboard_id"],
        },
    },
    {
        "name": "ha_update_dashboard",
        "description": "Update a Lovelace dashboard with a new config (views, cards, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "dashboard_id": {"type": "string", "description": "Dashboard URL path."},
                "config": {"type": "object", "description": "Full Lovelace config with views and cards."},
            },
            "required": ["dashboard_id", "config"],
        },
    },

    # ── HACS Tools ────────────────────────────────────────────────────────────
    {
        "name": "ha_hacs_list_repos",
        "description": "List installed HACS repositories (integrations, plugins, themes).",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category: 'integration', 'plugin', 'theme', or leave empty for all."}
            },
            "required": [],
        },
    },
    {
        "name": "ha_hacs_install",
        "description": (
            "Install a HACS repository by its full GitHub URL or slug. "
            "Triggers download and installation of the integration/plugin/theme."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repository": {"type": "string", "description": "GitHub repo URL or slug, e.g. 'hacs/integration' or 'https://github.com/user/repo'."},
                "category": {"type": "string", "description": "Category: 'integration', 'plugin', or 'theme'."},
            },
            "required": ["repository", "category"],
        },
    },
    {
        "name": "ha_hacs_search",
        "description": "Search HACS for available repositories by keyword.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term, e.g. 'mushroom cards', 'adaptive lighting'."}
            },
            "required": ["query"],
        },
    },

    # ── System & Diagnostics ──────────────────────────────────────────────────
    {
        "name": "ha_render_template",
        "description": "Render a Jinja2 template against live HA state.",
        "parameters": {
            "type": "object",
            "properties": {
                "template": {"type": "string", "description": "Jinja2 template string."}
            },
            "required": ["template"],
        },
    },
    {
        "name": "ha_get_history",
        "description": "Get state history for an entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "hours": {"type": "number", "description": "Hours to look back (default 24)."},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_get_error_log",
        "description": "Read the HA error log.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "ha_check_config",
        "description": "Validate the HA configuration (checks YAML for errors before reloading).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "ha_reload",
        "description": "Reload a specific HA domain/component (automations, scripts, scenes, groups, core config, themes, input_*, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "What to reload: 'automation', 'script', 'scene', 'group', 'core', 'theme', 'input_boolean', 'input_number', 'input_select', 'input_text', 'lovelace', etc."}
            },
            "required": ["domain"],
        },
    },
    {
        "name": "ha_restart",
        "description": "Restart Home Assistant. Use only when necessary (e.g. after installing new integrations).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "ha_get_addons",
        "description": "List all installed HA add-ons.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "ha_get_system_info",
        "description": "Get HA system info: version, OS, architecture, CPU, memory, storage.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "ha_install_custom_component",
        "description": (
            "Install a custom component by downloading it from a GitHub repo. "
            "Downloads the custom_components/<name>/ directory from the repo and "
            "places it in the HA config/custom_components/ directory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "github_url": {"type": "string", "description": "GitHub repo URL, e.g. 'https://github.com/user/ha-component'."},
                "component_name": {"type": "string", "description": "Name of the component directory (what goes in custom_components/)."},
            },
            "required": ["github_url", "component_name"],
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TOOL EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

async def execute_tool(name: str, inp: dict) -> str:
    try:
        # ── Entity & State ────────────────────────────────────────────────────
        if name == "ha_get_entities":
            states = await ha_get("/api/states")
            domain = inp.get("domain")
            results = []
            for s in states:
                eid = s["entity_id"]
                if domain and not eid.startswith(f"{domain}."):
                    continue
                results.append({
                    "entity_id": eid,
                    "state": s["state"],
                    "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                })
            if len(results) > 200:
                results = results[:200]
                results.append({"note": "Truncated. Filter by domain."})
            return json.dumps(results, indent=2)

        elif name == "ha_get_entity_state":
            return json.dumps(await ha_get(f"/api/states/{inp['entity_id']}"), indent=2)

        elif name == "ha_call_service":
            result = await ha_post(f"/api/services/{inp['domain']}/{inp['service']}", inp.get("service_data", {}))
            return json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)

        # ── YAML File Operations ──────────────────────────────────────────────
        elif name == "ha_read_file":
            fpath = Path(HA_CONFIG_DIR) / inp["path"]
            if not fpath.exists():
                return json.dumps({"error": f"File not found: {inp['path']}"})
            content = fpath.read_text()
            if len(content) > 10000:
                content = content[:10000] + "\n\n... (truncated, file is " + str(len(content)) + " chars)"
            return content

        elif name == "ha_write_file":
            fpath = Path(HA_CONFIG_DIR) / inp["path"]
            fpath.parent.mkdir(parents=True, exist_ok=True)
            # Backup existing file
            if fpath.exists():
                backup = fpath.with_suffix(fpath.suffix + ".bak")
                shutil.copy2(fpath, backup)
            fpath.write_text(inp["content"])
            return json.dumps({"success": True, "path": inp["path"], "size": len(inp["content"])})

        elif name == "ha_list_files":
            pattern = inp.get("pattern", "*")
            base = Path(HA_CONFIG_DIR)
            matches = sorted(str(p.relative_to(base)) for p in base.glob(pattern))
            if len(matches) > 200:
                matches = matches[:200] + ["... (truncated)"]
            return json.dumps(matches, indent=2)

        elif name == "ha_append_to_yaml":
            fpath = Path(HA_CONFIG_DIR) / inp["path"]
            existing = []
            if fpath.exists():
                content = fpath.read_text()
                if content.strip():
                    existing = yaml.safe_load(content) or []
            if not isinstance(existing, list):
                return json.dumps({"error": f"File is not a YAML list: {inp['path']}"})
            # Backup
            if fpath.exists():
                shutil.copy2(fpath, fpath.with_suffix(fpath.suffix + ".bak"))
            existing.append(inp["entry"])
            fpath.write_text(yaml.dump(existing, default_flow_style=False, sort_keys=False, allow_unicode=True))
            return json.dumps({"success": True, "total_entries": len(existing)})

        # ── Automation ────────────────────────────────────────────────────────
        elif name == "ha_list_automations":
            single_id = inp.get("automation_id")
            if single_id:
                state = await ha_get(f"/api/states/{single_id}")
                if isinstance(state, dict) and "entity_id" in state:
                    return json.dumps({
                        "entity_id": state["entity_id"],
                        "state": state["state"],
                        "alias": state.get("attributes", {}).get("friendly_name", ""),
                        "last_triggered": state.get("attributes", {}).get("last_triggered"),
                        "mode": state.get("attributes", {}).get("mode"),
                        "attributes": state.get("attributes", {}),
                    }, indent=2)
                return json.dumps({"error": f"Automation not found: {single_id}"})
            # List all automations
            states = await ha_get("/api/states")
            automations = []
            if isinstance(states, list):
                for s in states:
                    eid = s.get("entity_id", "")
                    if eid.startswith("automation."):
                        attrs = s.get("attributes", {})
                        automations.append({
                            "entity_id": eid,
                            "state": s["state"],
                            "alias": attrs.get("friendly_name", ""),
                            "last_triggered": attrs.get("last_triggered"),
                            "mode": attrs.get("mode", "single"),
                            "current": attrs.get("current", 0),
                        })
            return json.dumps({"count": len(automations), "automations": automations}, indent=2)

        elif name == "ha_create_automation":
            result = await ha_post(f"/api/config/automation/config/{inp['automation_id']}", inp["config"])
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)

        # ── Blueprints ────────────────────────────────────────────────────────
        elif name == "ha_create_blueprint":
            bp_dir = Path(HA_CONFIG_DIR) / "blueprints" / "automation" / "ai_programmer"
            bp_dir.mkdir(parents=True, exist_ok=True)
            bp_path = bp_dir / f"{inp['name']}.yaml"
            bp_path.write_text(inp["content"])
            return json.dumps({"success": True, "path": str(bp_path.relative_to(HA_CONFIG_DIR))})

        elif name == "ha_list_blueprints":
            bp_base = Path(HA_CONFIG_DIR) / "blueprints"
            blueprints = []
            if bp_base.exists():
                for bp in bp_base.rglob("*.yaml"):
                    blueprints.append(str(bp.relative_to(HA_CONFIG_DIR)))
            return json.dumps(blueprints, indent=2)

        # ── Dashboards / Lovelace ─────────────────────────────────────────────
        elif name == "ha_get_dashboards":
            dashboards = []
            # Method 1: Try the API
            try:
                result = await ha_get("/api/lovelace/dashboards")
                if isinstance(result, list):
                    dashboards = result
            except Exception as e:
                print(f"[WARN] Lovelace dashboards API failed: {e}")
            # Method 2: Read from .storage file (more reliable for add-ons)
            storage_dash = Path(HA_CONFIG_DIR) / ".storage" / "lovelace_dashboards"
            if storage_dash.exists():
                try:
                    sdata = json.loads(storage_dash.read_text())
                    for item in sdata.get("data", {}).get("items", []):
                        existing_paths = [d.get("url_path") for d in dashboards]
                        if item.get("url_path") not in existing_paths:
                            dashboards.append({
                                "id": item.get("id", ""),
                                "url_path": item.get("url_path", ""),
                                "title": item.get("title", ""),
                                "mode": item.get("mode", "storage"),
                                "source": ".storage"
                            })
                except Exception as e:
                    print(f"[WARN] .storage/lovelace_dashboards read failed: {e}")
            # Always include the default dashboard
            default_exists = any(d.get("url_path") == "lovelace" for d in dashboards)
            if not default_exists:
                dashboards.insert(0, {"id": None, "url_path": "lovelace", "title": "Overview (default)", "mode": "storage"})
            # Method 3: Check for YAML dashboard files
            dash_dir = Path(HA_CONFIG_DIR) / "dashboards"
            if dash_dir.exists():
                for f in dash_dir.glob("*.yaml"):
                    dashboards.append({"id": f.stem, "url_path": f.stem, "title": f.stem, "mode": "yaml", "file": str(f.relative_to(HA_CONFIG_DIR))})
            return json.dumps(dashboards, indent=2)

        elif name == "ha_get_dashboard_config":
            did = inp.get("dashboard_id", "lovelace")
            errors = []
            # Method 1: Try the API
            try:
                endpoint = "/api/lovelace/config" if did == "lovelace" else f"/api/lovelace/config/{did}"
                result = await ha_get(endpoint)
                return json.dumps(result, indent=2)
            except Exception as e:
                errors.append(f"API: {e}")
            # Method 2: Read from .storage files (HA stores UI dashboards here)
            storage_files = [
                Path(HA_CONFIG_DIR) / ".storage" / f"lovelace.{did}",
                Path(HA_CONFIG_DIR) / ".storage" / "lovelace",  # default dashboard
            ]
            for sf in storage_files:
                if sf.exists():
                    try:
                        sdata = json.loads(sf.read_text())
                        config = sdata.get("data", {}).get("config", sdata.get("data", {}))
                        return json.dumps(config, indent=2)
                    except Exception as e:
                        errors.append(f".storage/{sf.name}: {e}")
            # Method 3: YAML files
            yaml_paths = [
                Path(HA_CONFIG_DIR) / "dashboards" / f"{did}.yaml",
                Path(HA_CONFIG_DIR) / "ui-lovelace.yaml",
            ]
            for yp in yaml_paths:
                if yp.exists():
                    return yp.read_text()
            return json.dumps({"error": f"Could not load dashboard '{did}'. Tried: {'; '.join(errors)}. Check .storage and dashboards/ directory."})

        elif name == "ha_update_dashboard":
            did = inp.get("dashboard_id", "lovelace")
            endpoint = "/api/lovelace/config" if did == "lovelace" else f"/api/lovelace/config/{did}"
            result = await ha_post(endpoint, inp["config"])
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)

        # ── HACS ──────────────────────────────────────────────────────────────
        elif name == "ha_hacs_list_repos":
            # HACS exposes itself via websocket, but we can read its stored data
            hacs_path = Path(HA_CONFIG_DIR) / ".storage" / "hacs.repositories"
            if not hacs_path.exists():
                return json.dumps({"error": "HACS not installed or no repositories found."})
            data = json.loads(hacs_path.read_text())
            repos = data.get("data", {}).get("repositories", [])
            category = inp.get("category", "")
            results = []
            for r in repos:
                if category and r.get("category") != category:
                    continue
                results.append({
                    "name": r.get("name", ""),
                    "full_name": r.get("full_name", ""),
                    "category": r.get("category", ""),
                    "installed": r.get("installed", False),
                    "installed_version": r.get("installed_version", ""),
                    "available_version": r.get("available_version", ""),
                })
            return json.dumps(results[:100], indent=2)

        elif name == "ha_hacs_install":
            # Trigger HACS download via HA service call
            result = await ha_post("/api/services/hacs/install", {
                "repository": inp["repository"],
                "category": inp.get("category", "integration"),
            })
            return json.dumps({"success": True, "result": str(result)[:500]})

        elif name == "ha_hacs_search":
            # Read HACS default repos and search
            hacs_path = Path(HA_CONFIG_DIR) / ".storage" / "hacs.repositories"
            if not hacs_path.exists():
                return json.dumps({"error": "HACS not installed."})
            data = json.loads(hacs_path.read_text())
            repos = data.get("data", {}).get("repositories", [])
            query = inp.get("query", "").lower()
            matches = []
            for r in repos:
                name = (r.get("name", "") + " " + r.get("description", "")).lower()
                if query in name or query in r.get("full_name", "").lower():
                    matches.append({
                        "name": r.get("name", ""),
                        "full_name": r.get("full_name", ""),
                        "category": r.get("category", ""),
                        "description": r.get("description", "")[:200],
                        "installed": r.get("installed", False),
                    })
            return json.dumps(matches[:30], indent=2)

        # ── System & Diagnostics ──────────────────────────────────────────────
        elif name == "ha_render_template":
            result = await ha_post("/api/template", {"template": inp["template"]})
            return str(result)

        elif name == "ha_get_history":
            hours = inp.get("hours", 24)
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
            result = await ha_get(f"/api/history/period/{since}?filter_entity_id={inp['entity_id']}")
            if result and isinstance(result, list) and len(result) > 0:
                entries = result[0] if isinstance(result[0], list) else result
                summary = [{"state": e.get("state"), "last_changed": e.get("last_changed")} for e in entries[-50:]]
                return json.dumps(summary, indent=2)
            return json.dumps(result, indent=2)

        elif name == "ha_get_error_log":
            r = await ha_client.get(f"{HA_URL}/api/error_log", headers=ha_headers())
            text = r.text
            if len(text) > 5000:
                text = "...(truncated)...\n" + text[-5000:]
            return text

        elif name == "ha_check_config":
            result = await ha_post("/api/config/core/check_config")
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)

        elif name == "ha_reload":
            domain = inp["domain"]
            if domain == "core":
                result = await ha_post("/api/services/homeassistant/reload_core_config")
            elif domain == "lovelace":
                result = await ha_post("/api/services/lovelace/reload_resources")
            else:
                result = await ha_post(f"/api/services/{domain}/reload")
            return json.dumps({"success": True, "reloaded": domain})

        elif name == "ha_restart":
            result = await ha_post("/api/services/homeassistant/restart")
            return json.dumps({"success": True, "message": "HA restart triggered."})

        elif name == "ha_get_addons":
            try:
                result = await supervisor_get("/addons")
                addons = result.get("data", {}).get("addons", [])
                return json.dumps([{
                    "name": a.get("name"),
                    "slug": a.get("slug"),
                    "state": a.get("state"),
                    "version": a.get("version"),
                    "update_available": a.get("update_available", False),
                } for a in addons], indent=2)
            except Exception:
                return json.dumps({"error": "Supervisor API not available (not running as add-on?)."})

        elif name == "ha_get_system_info":
            try:
                info = await supervisor_get("/info")
                host = await supervisor_get("/host/info")
                return json.dumps({
                    "ha_version": info.get("data", {}).get("homeassistant", ""),
                    "supervisor_version": info.get("data", {}).get("supervisor", ""),
                    "os": host.get("data", {}).get("operating_system", ""),
                    "hostname": host.get("data", {}).get("hostname", ""),
                    "chassis": host.get("data", {}).get("chassis", ""),
                    "cpe": host.get("data", {}).get("cpe", ""),
                }, indent=2)
            except Exception:
                config = await ha_get("/api/config")
                return json.dumps(config, indent=2)

        elif name == "ha_install_custom_component":
            # Download a custom component from GitHub
            repo_url = inp["github_url"].rstrip("/")
            comp_name = inp["component_name"]
            dest = Path(HA_CONFIG_DIR) / "custom_components" / comp_name
            dest.mkdir(parents=True, exist_ok=True)

            # Use GitHub API to get the directory listing
            # Parse owner/repo from URL
            match = re.match(r"https://github\.com/([^/]+)/([^/]+)", repo_url)
            if not match:
                return json.dumps({"error": "Invalid GitHub URL."})
            owner, repo = match.groups()

            # Try to download the component files via GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/custom_components/{comp_name}"
            r = await ha_client.get(api_url)
            if r.status_code != 200:
                return json.dumps({"error": f"Could not find custom_components/{comp_name} in the repo. Status: {r.status_code}"})

            files = r.json()
            downloaded = []
            for f in files:
                if f["type"] == "file" and f.get("download_url"):
                    content_r = await ha_client.get(f["download_url"])
                    (dest / f["name"]).write_text(content_r.text)
                    downloaded.append(f["name"])

            return json.dumps({
                "success": True,
                "component": comp_name,
                "files_installed": downloaded,
                "note": "Restart HA to load the new component.",
            })

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HA API error {e.response.status_code}: {e.response.text[:500]}"})
    except Exception as e:
        traceback.print_exc()
        return json.dumps({"error": str(e)})


# ══════════════════════════════════════════════════════════════════════════════
# TOOL FORMAT CONVERTERS
# ══════════════════════════════════════════════════════════════════════════════

def tools_for_openai():
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in HA_TOOLS]

def tools_for_gemini():
    return [{"function_declarations": [{"name": t["name"], "description": t["description"], "parameters": t["parameters"]} for t in HA_TOOLS]}]

def tools_for_anthropic():
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in HA_TOOLS]


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are HA AI Programmer, an expert Home Assistant developer with full system access.

You have powerful tools to:
- Read and write ANY file in the HA config directory (YAML, JSON, Python, etc.)
- Control all devices via service calls
- List and inspect all existing automations (use ha_list_automations FIRST before creating new ones)
- Create automations, scripts, and scenes
- Generate reusable Blueprints
- Build and modify Lovelace dashboards (add cards, views, themes)
- Install HACS repositories and custom components from GitHub
- Check config validity, reload components, and restart HA
- Read error logs, entity history, and system info
- Render Jinja2 templates

IMPORTANT GUIDELINES:
- Before creating any automation, ALWAYS call ha_list_automations first to see what already exists.
- Before editing ANY file, always READ it first to understand the current state.
- After writing a file, use ha_check_config to validate before reloading.
- After creating/editing automations, reload them with ha_reload.
- When installing custom components, remind the user a restart is needed.
- Always backup files before overwriting (the write tool does this automatically).
- Use modern HA syntax: plural keys (triggers, conditions, actions), target instead of entity_id in data.
- Explain what you're doing and why, in plain language.
- When creating dashboards, use modern card types and explain the layout.
- When generating blueprints, include clear input descriptions and selectors.
- Be proactive about suggesting improvements you notice.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER CHAT IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

conversations = {}  # type: dict[str, list]

# ── Chat history persistence (survives tab reloads) ──────────────────────
CHAT_HISTORY_FILE = Path("/data/chat_history.json")
chat_display_history = {}  # type: dict[str, list]  # session_id -> [{role, content, tool_actions}]

def _load_chat_history():
    global chat_display_history
    try:
        if CHAT_HISTORY_FILE.exists():
            chat_display_history = json.loads(CHAT_HISTORY_FILE.read_text())
    except Exception:
        chat_display_history = {}

def _save_chat_history():
    try:
        CHAT_HISTORY_FILE.write_text(json.dumps(chat_display_history))
    except Exception:
        pass

_load_chat_history()

async def chat_openai(messages, tool_actions):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    tools = tools_for_openai()
    oai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages:
        if m["role"] == "user":
            if isinstance(m["content"], str):
                oai_messages.append({"role": "user", "content": m["content"]})
            elif isinstance(m["content"], list):
                for tr in m["content"]:
                    oai_messages.append({"role": "tool", "tool_call_id": tr["tool_call_id"], "content": tr["content"]})
        elif m["role"] == "assistant":
            oai_messages.append(m["_openai_msg"])
    while True:
        response = client.chat.completions.create(model=OPENAI_MODEL, messages=oai_messages, tools=tools, max_tokens=4096)
        msg = response.choices[0].message
        oai_msg_dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            oai_msg_dict["tool_calls"] = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
        oai_messages.append(oai_msg_dict)
        messages.append({"role": "assistant", "_openai_msg": oai_msg_dict, "content": msg.content or ""})
        if not msg.tool_calls:
            return msg.content or ""
        entries = []
        for tc in msg.tool_calls:
            fn_args = json.loads(tc.function.arguments)
            result_str = await execute_tool(tc.function.name, fn_args)
            tool_actions.append({"tool": tc.function.name, "input": fn_args, "result_preview": result_str[:300]})
            oai_messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})
            entries.append({"tool_call_id": tc.id, "content": result_str})
        messages.append({"role": "user", "content": entries})


async def chat_gemini(messages, tool_actions):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)
    tools_def = tools_for_gemini()
    contents = []
    for m in messages:
        if m["role"] == "user":
            if isinstance(m["content"], str):
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m["content"])]))
            elif isinstance(m["content"], list):
                parts = []
                for tr in m["content"]:
                    try:
                        rd = json.loads(tr["content"])
                    except:
                        rd = {"result": tr["content"]}
                    parts.append(types.Part.from_function_response(name=tr["function_name"], response=rd if isinstance(rd, dict) else {"result": rd}))
                contents.append(types.Content(role="user", parts=parts))
        elif m["role"] == "assistant" and "_gemini_parts" in m:
            contents.append(types.Content(role="model", parts=m["_gemini_parts"]))
    while True:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=contents, config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=tools_def, temperature=0.7))
        parts = response.candidates[0].content.parts
        fn_calls = [p for p in parts if p.function_call and p.function_call.name]
        text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
        contents.append(response.candidates[0].content)
        messages.append({"role": "assistant", "_gemini_parts": parts, "content": "\n".join(text_parts) if text_parts else ""})
        if not fn_calls:
            return "\n".join(text_parts) if text_parts else ""
        result_parts, entries = [], []
        for fc in fn_calls:
            fn_args = dict(fc.function_call.args) if fc.function_call.args else {}
            result_str = await execute_tool(fc.function_call.name, fn_args)
            tool_actions.append({"tool": fc.function_call.name, "input": fn_args, "result_preview": result_str[:300]})
            try:
                rd = json.loads(result_str)
            except:
                rd = {"result": result_str}
            result_parts.append(types.Part.from_function_response(name=fc.function_call.name, response=rd if isinstance(rd, dict) else {"result": rd}))
            entries.append({"function_name": fc.function_call.name, "content": result_str})
        contents.append(types.Content(role="user", parts=result_parts))
        messages.append({"role": "user", "content": entries})


async def chat_anthropic(messages, tool_actions):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tools = tools_for_anthropic()
    while True:
        response = client.messages.create(model=ANTHROPIC_MODEL, max_tokens=4096, system=SYSTEM_PROMPT, tools=tools, messages=messages)
        ac = response.content
        messages.append({"role": "assistant", "content": ac})
        tool_uses = [b for b in ac if b.type == "tool_use"]
        if not tool_uses:
            return "\n".join(b.text for b in ac if hasattr(b, "text"))
        results = []
        for tu in tool_uses:
            rs = await execute_tool(tu.name, tu.input)
            tool_actions.append({"tool": tu.name, "input": tu.input, "result_preview": rs[:300]})
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": rs})
        messages.append({"role": "user", "content": results})


async def chat_ollama(messages, tool_actions):
    from openai import OpenAI
    client = OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")
    tools = tools_for_openai()
    oai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages:
        if m["role"] == "user":
            if isinstance(m["content"], str):
                oai_messages.append({"role": "user", "content": m["content"]})
            elif isinstance(m["content"], list):
                for tr in m["content"]:
                    oai_messages.append({"role": "tool", "tool_call_id": tr["tool_call_id"], "content": tr["content"]})
        elif m["role"] == "assistant":
            oai_messages.append(m["_openai_msg"])
    while True:
        try:
            response = client.chat.completions.create(model=OLLAMA_MODEL, messages=oai_messages, tools=tools)
        except:
            response = client.chat.completions.create(model=OLLAMA_MODEL, messages=oai_messages)
        msg = response.choices[0].message
        oai_msg_dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            oai_msg_dict["tool_calls"] = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
        oai_messages.append(oai_msg_dict)
        messages.append({"role": "assistant", "_openai_msg": oai_msg_dict, "content": msg.content or ""})
        if not msg.tool_calls:
            return msg.content or ""
        entries = []
        for tc in msg.tool_calls:
            fn_args = json.loads(tc.function.arguments)
            result_str = await execute_tool(tc.function.name, fn_args)
            tool_actions.append({"tool": tc.function.name, "input": fn_args, "result_preview": result_str[:300]})
            oai_messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})
            entries.append({"tool_call_id": tc.id, "content": result_str})
        messages.append({"role": "user", "content": entries})


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "")
    session_id = body.get("session_id", "default")
    if session_id not in conversations:
        conversations[session_id] = []
    conversations[session_id].append({"role": "user", "content": user_message})
    messages = conversations[session_id]
    tool_actions = []
    try:
        providers = {"openai": chat_openai, "gemini": chat_gemini, "anthropic": chat_anthropic, "ollama": chat_ollama}
        fn = providers.get(AI_PROVIDER)
        if not fn:
            return JSONResponse({"error": f"Unknown provider: {AI_PROVIDER}"}, status_code=400)
        final_text = await fn(messages, tool_actions)
        if len(conversations[session_id]) > 40:
            conversations[session_id] = conversations[session_id][-40:]
        # Save to display history
        if session_id not in chat_display_history:
            chat_display_history[session_id] = []
        chat_display_history[session_id].append({"role": "user", "content": user_message})
        chat_display_history[session_id].append({"role": "assistant", "content": final_text, "tool_actions": tool_actions})
        if len(chat_display_history[session_id]) > 100:
            chat_display_history[session_id] = chat_display_history[session_id][-100:]
        _save_chat_history()
        return JSONResponse({"response": final_text, "tool_actions": tool_actions, "session_id": session_id})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": f"{AI_PROVIDER.title()} error: {str(e)}"}, status_code=502)


@app.get("/api/chat-history")
async def get_chat_history(request: Request):
    session_id = request.query_params.get("session_id", "default")
    return JSONResponse({"messages": chat_display_history.get(session_id, []), "session_id": session_id})

@app.delete("/api/chat-history")
async def clear_chat_history(request: Request):
    session_id = request.query_params.get("session_id", "default")
    chat_display_history.pop(session_id, None)
    conversations.pop(session_id, None)
    _save_chat_history()
    return JSONResponse({"ok": True})

@app.get("/api/ha-status")
async def ha_status():
    if not HA_URL or not HA_TOKEN:
        return JSONResponse({"connected": False, "reason": "HA_URL or HA_TOKEN not set."})
    try:
        result = await ha_get("/api/")
        return JSONResponse({"connected": True, "ha": result})
    except Exception as e:
        return JSONResponse({"connected": False, "reason": str(e)})


@app.get("/api/provider")
async def get_provider():
    models = {"openai": OPENAI_MODEL, "gemini": GEMINI_MODEL, "anthropic": ANTHROPIC_MODEL, "ollama": OLLAMA_MODEL}
    return JSONResponse({
        "provider": AI_PROVIDER,
        "model": models.get(AI_PROVIDER, "unknown"),
        "has_key": bool(
            (AI_PROVIDER == "openai" and OPENAI_API_KEY) or
            (AI_PROVIDER == "gemini" and GEMINI_API_KEY) or
            (AI_PROVIDER == "anthropic" and ANTHROPIC_API_KEY) or
            (AI_PROVIDER == "ollama")
        ),
        "ha_url": HA_URL or "",
    })


@app.post("/api/settings")
async def update_settings(request: Request):
    global AI_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY
    global OPENAI_MODEL, GEMINI_MODEL, ANTHROPIC_MODEL
    global OLLAMA_URL, OLLAMA_MODEL
    body = await request.json()
    if "provider" in body: AI_PROVIDER = body["provider"].lower()
    if body.get("openai_api_key"): OPENAI_API_KEY = body["openai_api_key"]
    if body.get("gemini_api_key"): GEMINI_API_KEY = body["gemini_api_key"]
    if body.get("anthropic_api_key"): ANTHROPIC_API_KEY = body["anthropic_api_key"]
    if body.get("openai_model"): OPENAI_MODEL = body["openai_model"]
    if body.get("gemini_model"): GEMINI_MODEL = body["gemini_model"]
    if body.get("anthropic_model"): ANTHROPIC_MODEL = body["anthropic_model"]
    if body.get("ollama_url"): OLLAMA_URL = body["ollama_url"]
    if body.get("ollama_model"): OLLAMA_MODEL = body["ollama_model"]
    conversations.clear()
    models = {"openai": OPENAI_MODEL, "gemini": GEMINI_MODEL, "anthropic": ANTHROPIC_MODEL, "ollama": OLLAMA_MODEL}
    return JSONResponse({"ok": True, "provider": AI_PROVIDER, "model": models.get(AI_PROVIDER)})


@app.get("/api/ha-entities-summary")
async def ha_entities_summary():
    try:
        states = await ha_get("/api/states")
        counts = {}
        for s in states:
            d = s["entity_id"].split(".")[0]
            counts[d] = counts.get(d, 0) + 1
        return JSONResponse({"counts": dict(sorted(counts.items())), "total": len(states)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/debug")
async def debug_info():
    """Debug endpoint to diagnose file access and API issues."""
    info = {
        "ha_url": HA_URL,
        "ha_token_set": bool(HA_TOKEN),
        "ha_token_length": len(HA_TOKEN) if HA_TOKEN else 0,
        "config_dir": HA_CONFIG_DIR,
        "config_dir_exists": Path(HA_CONFIG_DIR).exists(),
    }
    # Check what's in /config
    config_path = Path(HA_CONFIG_DIR)
    if config_path.exists():
        try:
            info["config_files"] = sorted([f.name for f in config_path.iterdir()])[:50]
        except Exception as e:
            info["config_files_error"] = str(e)
    # Check .storage directory
    storage_path = config_path / ".storage"
    if storage_path.exists():
        try:
            storage_files = sorted([f.name for f in storage_path.iterdir() if "lovelace" in f.name.lower()])
            info["storage_lovelace_files"] = storage_files
        except Exception as e:
            info["storage_error"] = str(e)
    else:
        info["storage_exists"] = False
    # Test HA API
    try:
        result = await ha_get("/api/")
        info["ha_api_test"] = result
    except Exception as e:
        info["ha_api_error"] = str(e)
    # Test lovelace dashboards API
    try:
        result = await ha_get("/api/lovelace/dashboards")
        info["lovelace_dashboards_api"] = result
    except Exception as e:
        info["lovelace_dashboards_error"] = str(e)
    # Test default lovelace config API
    try:
        result = await ha_get("/api/lovelace/config")
        info["lovelace_config_keys"] = list(result.keys()) if isinstance(result, dict) else type(result).__name__
    except Exception as e:
        info["lovelace_config_error"] = str(e)
    return JSONResponse(info)


@app.get("/")
async def index():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text())


if __name__ == "__main__":
    models = {"openai": OPENAI_MODEL, "gemini": GEMINI_MODEL, "anthropic": ANTHROPIC_MODEL, "ollama": OLLAMA_MODEL}
    print(f"\n🏠 HA AI Programmer")
    print(f"   Provider: {AI_PROVIDER.upper()} ({models.get(AI_PROVIDER, '?')})")
    print(f"   Config dir: {HA_CONFIG_DIR}")
    print(f"   Open http://localhost:8099 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8099)

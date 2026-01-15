"""FastAPI application for Vizio TV control."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from .smartcast import SmartCastClient, TVConfig, KEYS
from .config import Settings, load_tvs, save_tvs, TVEntry

settings = Settings()
tv_configs: dict[str, TVEntry] = {}
tv_clients: dict[str, SmartCastClient] = {}

# Pairing state (temporary)
pairing_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load config on startup, cleanup on shutdown."""
    global tv_configs
    tv_configs = load_tvs(settings.config_file)

    # Create clients for configured TVs
    for tv_id, config in tv_configs.items():
        tv_clients[tv_id] = SmartCastClient(TVConfig(
            host=config.host,
            port=config.port,
            auth_token=config.auth_token,
        ))

    yield

    # Cleanup
    for client in tv_clients.values():
        await client.close()


app = FastAPI(
    title="Vizio Control",
    description="Web-based Vizio SmartCast TV controller",
    version="0.1.0",
    lifespan=lifespan,
)


# ============ API Reference (generated from routes) ============

def generate_api_reference():
    """Generate API reference from actual FastAPI routes."""
    from fastapi.routing import APIRoute

    endpoints = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            # Skip the reference endpoints themselves
            if route.path in ["/api", "/api/reference"]:
                continue

            methods = [m for m in route.methods if m != "HEAD"]
            for method in methods:
                endpoints.append({
                    "method": method,
                    "path": route.path,
                    "description": route.description or route.name.replace("_", " ").title(),
                })

    return sorted(endpoints, key=lambda x: (x["path"], x["method"]))


@app.get("/api")
async def api_reference():
    """Auto-generated API reference from actual routes."""
    endpoints = generate_api_reference()

    # Group by path prefix
    groups: dict[str, list] = {}
    for ep in endpoints:
        parts = ep["path"].split("/")
        # /api/tvs/{tv_id}/power/on -> "power"
        if len(parts) >= 5:
            group = parts[4]  # power, volume, nav, picture, etc.
        elif len(parts) >= 3:
            group = parts[2]  # tvs, keys
        else:
            group = "other"
        groups.setdefault(group, []).append(ep)

    return {
        "base_url": "/api",
        "configured_tvs": list(tv_configs.keys()),
        "endpoints_by_category": groups,
        "total_endpoints": len(endpoints),
    }


@app.get("/api/reference")
async def api_reference_simple():
    """Flat list of all endpoints for easy parsing."""
    endpoints = generate_api_reference()
    return {
        "tvs": list(tv_configs.keys()),
        "endpoints": [f"{ep['method']} {ep['path']}" for ep in endpoints],
    }


# ============ Helper Functions ============

def get_client(tv_id: str) -> SmartCastClient:
    """Get TV client by ID."""
    if tv_id not in tv_clients:
        raise HTTPException(status_code=404, detail=f"TV '{tv_id}' not found")
    return tv_clients[tv_id]


# ============ Pydantic Models ============

class AddTVRequest(BaseModel):
    name: str
    host: str
    port: int = 7345


class PairRequest(BaseModel):
    pin: str


class SetValueRequest(BaseModel):
    value: int | str


class SetInputRequest(BaseModel):
    input_name: str


# ============ TV Management ============

@app.get("/api/tvs")
async def list_tvs():
    """List all configured TVs."""
    return {
        tv_id: {
            "name": config.name,
            "host": config.host,
            "port": config.port,
            "paired": config.auth_token is not None,
        }
        for tv_id, config in tv_configs.items()
    }


@app.post("/api/tvs/{tv_id}")
async def add_tv(tv_id: str, req: AddTVRequest):
    """Add a new TV."""
    if tv_id in tv_configs:
        raise HTTPException(status_code=409, detail=f"TV '{tv_id}' already exists")

    config = TVEntry(name=req.name, host=req.host, port=req.port)
    tv_configs[tv_id] = config
    tv_clients[tv_id] = SmartCastClient(TVConfig(
        host=config.host,
        port=config.port,
    ))
    save_tvs(settings.config_file, tv_configs)
    return {"status": "ok", "tv_id": tv_id}


@app.delete("/api/tvs/{tv_id}")
async def remove_tv(tv_id: str):
    """Remove a TV."""
    if tv_id not in tv_configs:
        raise HTTPException(status_code=404, detail=f"TV '{tv_id}' not found")

    if tv_id in tv_clients:
        await tv_clients[tv_id].close()
        del tv_clients[tv_id]

    del tv_configs[tv_id]
    save_tvs(settings.config_file, tv_configs)
    return {"status": "ok"}


# ============ Pairing ============

@app.post("/api/tvs/{tv_id}/pair/start")
async def start_pairing(tv_id: str):
    """Start pairing - displays PIN on TV."""
    client = get_client(tv_id)
    result = await client.start_pairing()

    if result.get("STATUS", {}).get("RESULT") == "SUCCESS":
        pairing_state[tv_id] = result["ITEM"]["PAIRING_REQ_TOKEN"]
        return {"status": "ok", "message": "PIN displayed on TV"}

    raise HTTPException(status_code=500, detail=result.get("STATUS", {}).get("DETAIL", "Unknown error"))


@app.post("/api/tvs/{tv_id}/pair/complete")
async def complete_pairing(tv_id: str, req: PairRequest):
    """Complete pairing with PIN."""
    client = get_client(tv_id)

    if tv_id not in pairing_state:
        raise HTTPException(status_code=400, detail="No pairing in progress")

    token = pairing_state[tv_id]
    result = await client.complete_pairing(req.pin, token)

    if result.get("STATUS", {}).get("RESULT") == "SUCCESS":
        # Save auth token
        tv_configs[tv_id].auth_token = client.config.auth_token
        save_tvs(settings.config_file, tv_configs)
        del pairing_state[tv_id]
        return {"status": "ok", "message": "Paired successfully"}

    raise HTTPException(status_code=400, detail=result.get("STATUS", {}).get("DETAIL", "Pairing failed"))


# ============ Power ============

@app.post("/api/tvs/{tv_id}/power/on")
async def power_on(tv_id: str):
    """Turn TV on."""
    return await get_client(tv_id).power_on()


@app.post("/api/tvs/{tv_id}/power/off")
async def power_off(tv_id: str):
    """Turn TV off."""
    return await get_client(tv_id).power_off()


@app.post("/api/tvs/{tv_id}/power/toggle")
async def power_toggle(tv_id: str):
    """Toggle TV power."""
    return await get_client(tv_id).power_toggle()


@app.get("/api/tvs/{tv_id}/power")
async def get_power(tv_id: str):
    """Get power state."""
    return await get_client(tv_id).get_power_state()


# ============ Volume ============

@app.post("/api/tvs/{tv_id}/volume/up")
async def volume_up(tv_id: str, amount: int = 1):
    """Increase volume."""
    return await get_client(tv_id).volume_up(amount)


@app.post("/api/tvs/{tv_id}/volume/down")
async def volume_down(tv_id: str, amount: int = 1):
    """Decrease volume."""
    return await get_client(tv_id).volume_down(amount)


@app.post("/api/tvs/{tv_id}/mute/toggle")
async def mute_toggle(tv_id: str):
    """Toggle mute."""
    return await get_client(tv_id).mute_toggle()


@app.post("/api/tvs/{tv_id}/mute/on")
async def mute_on(tv_id: str):
    """Mute."""
    return await get_client(tv_id).mute_on()


@app.post("/api/tvs/{tv_id}/mute/off")
async def mute_off(tv_id: str):
    """Unmute."""
    return await get_client(tv_id).mute_off()


# ============ Picture Settings ============

@app.get("/api/tvs/{tv_id}/picture")
async def get_picture_settings(tv_id: str):
    """Get picture settings."""
    return await get_client(tv_id).get_picture_settings()


@app.post("/api/tvs/{tv_id}/picture/backlight")
async def set_backlight(tv_id: str, req: SetValueRequest):
    """Set backlight (0-100)."""
    return await get_client(tv_id).set_backlight(int(req.value))


@app.post("/api/tvs/{tv_id}/picture/brightness")
async def set_brightness(tv_id: str, req: SetValueRequest):
    """Set brightness (0-100)."""
    return await get_client(tv_id).set_brightness(int(req.value))


@app.post("/api/tvs/{tv_id}/picture/contrast")
async def set_contrast(tv_id: str, req: SetValueRequest):
    """Set contrast (0-100)."""
    return await get_client(tv_id).set_contrast(int(req.value))


@app.post("/api/tvs/{tv_id}/picture/color")
async def set_color(tv_id: str, req: SetValueRequest):
    """Set color (0-100)."""
    return await get_client(tv_id).set_picture_setting("color", int(req.value))


@app.post("/api/tvs/{tv_id}/picture/sharpness")
async def set_sharpness(tv_id: str, req: SetValueRequest):
    """Set sharpness (0-100)."""
    return await get_client(tv_id).set_picture_setting("sharpness", int(req.value))


@app.post("/api/tvs/{tv_id}/picture/mode")
async def set_picture_mode(tv_id: str, req: SetValueRequest):
    """Set picture mode (Vivid, Bright, Calibrated, Calibrated Dark, Game, Sports)."""
    return await get_client(tv_id).set_picture_mode(str(req.value))


# ============ Audio Settings ============

@app.get("/api/tvs/{tv_id}/audio")
async def get_audio_settings(tv_id: str):
    """Get audio settings."""
    return await get_client(tv_id).get_audio_settings()


# ============ Inputs ============

@app.get("/api/tvs/{tv_id}/inputs")
async def get_inputs(tv_id: str):
    """Get available inputs."""
    return await get_client(tv_id).get_inputs()


@app.get("/api/tvs/{tv_id}/input")
async def get_current_input(tv_id: str):
    """Get current input."""
    return await get_client(tv_id).get_current_input()


@app.post("/api/tvs/{tv_id}/input")
async def set_input(tv_id: str, req: SetInputRequest):
    """Set input by name."""
    # Get hashval from inputs list
    inputs_resp = await get_client(tv_id).get_inputs()
    hashval = None
    for item in inputs_resp.get("ITEMS", []):
        if item.get("NAME") == req.input_name or item.get("VALUE", {}).get("NAME") == req.input_name:
            hashval = item.get("HASHVAL")
            break

    if hashval is None:
        hashval = 0  # Fallback

    return await get_client(tv_id).set_input(req.input_name, hashval)


@app.post("/api/tvs/{tv_id}/input/cycle")
async def cycle_input(tv_id: str):
    """Cycle to next input."""
    return await get_client(tv_id).cycle_input()


# ============ Navigation ============

@app.post("/api/tvs/{tv_id}/nav/{direction}")
async def navigate(tv_id: str, direction: str):
    """Navigate: up, down, left, right, ok, back, home, menu, exit."""
    client = get_client(tv_id)
    method_map = {
        "up": client.nav_up,
        "down": client.nav_down,
        "left": client.nav_left,
        "right": client.nav_right,
        "ok": client.nav_ok,
        "select": client.nav_ok,
        "back": client.nav_back,
        "home": client.nav_home,
        "menu": client.nav_menu,
        "exit": client.nav_exit,
    }

    if direction not in method_map:
        raise HTTPException(status_code=400, detail=f"Unknown direction: {direction}")

    return await method_map[direction]()


# ============ Media Controls ============

@app.post("/api/tvs/{tv_id}/media/{action}")
async def media_control(tv_id: str, action: str):
    """Media control: play, pause, stop, rewind, fast_forward, prev, next."""
    client = get_client(tv_id)
    method_map = {
        "play": client.media_play,
        "pause": client.media_pause,
        "stop": client.media_stop,
        "rewind": client.media_rewind,
        "fast_forward": client.media_fast_forward,
        "ff": client.media_fast_forward,
        "prev": client.media_prev,
        "next": client.media_next,
    }

    if action not in method_map:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    return await method_map[action]()


# ============ Raw Key Command ============

@app.post("/api/tvs/{tv_id}/key/{key_name}")
async def send_key(tv_id: str, key_name: str):
    """Send a raw key command by name."""
    if key_name not in KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown key: {key_name}. Available: {list(KEYS.keys())}"
        )
    return await get_client(tv_id).send_key(key_name)


@app.get("/api/keys")
async def list_keys():
    """List all available key names."""
    return {"keys": list(KEYS.keys())}


# ============ Web UI ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the web UI."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return """
    <html>
    <head><title>Vizio Control</title></head>
    <body>
        <h1>Vizio Control</h1>
        <p>Static files not found. Please check installation.</p>
        <p><a href="/docs">API Documentation</a></p>
    </body>
    </html>
    """


# Mount static files if directory exists
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

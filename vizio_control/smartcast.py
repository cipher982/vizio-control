"""Vizio SmartCast API client."""

import httpx
from typing import Any
from dataclasses import dataclass
from enum import IntEnum


class Codeset(IntEnum):
    """SmartCast remote codesets."""
    ASCII = 0
    KEY_MODIFIER = 1
    TRANSPORT = 2
    DPAD = 3
    NAV = 4
    AUDIO = 5
    VIDEO = 6
    INPUT = 7
    CHANNEL = 8
    COLOR = 9
    LAUNCH = 10
    POWER = 11
    THREED = 12
    CC = 13
    FACTORY = 14


# Key codes by codeset
KEYS = {
    # D-Pad (codeset 3)
    "down": (Codeset.DPAD, 0),
    "left": (Codeset.DPAD, 1),
    "ok": (Codeset.DPAD, 2),
    "select": (Codeset.DPAD, 2),
    "right": (Codeset.DPAD, 7),
    "up": (Codeset.DPAD, 8),

    # Nav (codeset 4)
    "back": (Codeset.NAV, 0),
    "exit": (Codeset.NAV, 1),
    "home": (Codeset.NAV, 3),
    "menu": (Codeset.NAV, 8),

    # Audio (codeset 5)
    "vol_down": (Codeset.AUDIO, 0),
    "vol_up": (Codeset.AUDIO, 1),
    "mute_off": (Codeset.AUDIO, 2),
    "mute_on": (Codeset.AUDIO, 3),
    "mute_toggle": (Codeset.AUDIO, 4),

    # Video (codeset 6)
    "pic_mode": (Codeset.VIDEO, 0),
    "wide_mode": (Codeset.VIDEO, 1),
    "wide_cycle": (Codeset.VIDEO, 2),

    # Input (codeset 7)
    "input_cycle": (Codeset.INPUT, 1),

    # Channel (codeset 8)
    "ch_down": (Codeset.CHANNEL, 0),
    "ch_up": (Codeset.CHANNEL, 1),
    "ch_prev": (Codeset.CHANNEL, 2),

    # Power (codeset 11)
    "power_off": (Codeset.POWER, 0),
    "power_on": (Codeset.POWER, 1),
    "power_toggle": (Codeset.POWER, 2),

    # Transport (codeset 2) - media controls
    "play": (Codeset.TRANSPORT, 0),
    "pause": (Codeset.TRANSPORT, 1),
    "stop": (Codeset.TRANSPORT, 2),
    "rew": (Codeset.TRANSPORT, 3),
    "ff": (Codeset.TRANSPORT, 4),
    "prev": (Codeset.TRANSPORT, 5),
    "next": (Codeset.TRANSPORT, 6),
}


@dataclass
class TVConfig:
    """TV connection configuration."""
    host: str
    port: int = 7345
    auth_token: str | None = None
    device_id: str = "vizio-control"
    device_name: str = "Vizio Control"


class SmartCastClient:
    """Client for Vizio SmartCast API."""

    def __init__(self, config: TVConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=f"https://{config.host}:{config.port}",
            verify=False,  # TV uses self-signed cert
            timeout=10.0,
        )

    @property
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.auth_token:
            headers["AUTH"] = self.config.auth_token
        return headers

    async def close(self):
        await self._client.aclose()

    # ============ Pairing ============

    async def start_pairing(self) -> dict:
        """Start pairing - displays PIN on TV."""
        resp = await self._client.put(
            "/pairing/start",
            headers=self._headers,
            json={
                "DEVICE_ID": self.config.device_id,
                "DEVICE_NAME": self.config.device_name,
            }
        )
        return resp.json()

    async def complete_pairing(self, pin: str, pairing_token: int) -> dict:
        """Complete pairing with PIN from TV screen."""
        resp = await self._client.put(
            "/pairing/pair",
            headers=self._headers,
            json={
                "DEVICE_ID": self.config.device_id,
                "CHALLENGE_TYPE": 1,
                "RESPONSE_VALUE": pin,
                "PAIRING_REQ_TOKEN": pairing_token,
            }
        )
        data = resp.json()
        if data.get("STATUS", {}).get("RESULT") == "SUCCESS":
            self.config.auth_token = data["ITEM"]["AUTH_TOKEN"]
        return data

    async def cancel_pairing(self) -> dict:
        """Cancel pairing in progress."""
        resp = await self._client.put("/pairing/cancel", headers=self._headers)
        return resp.json()

    # ============ Power ============

    async def get_power_state(self) -> dict:
        """Get current power state."""
        resp = await self._client.get("/state/device/power_mode", headers=self._headers)
        return resp.json()

    async def power_on(self) -> dict:
        return await self.send_key("power_on")

    async def power_off(self) -> dict:
        return await self.send_key("power_off")

    async def power_toggle(self) -> dict:
        return await self.send_key("power_toggle")

    # ============ Remote Keys ============

    async def send_key(self, key_name: str, action: str = "KEYPRESS") -> dict:
        """Send a remote key command."""
        if key_name not in KEYS:
            raise ValueError(f"Unknown key: {key_name}. Available: {list(KEYS.keys())}")

        codeset, code = KEYS[key_name]
        return await self.send_key_raw(codeset, code, action)

    async def send_key_raw(self, codeset: int, code: int, action: str = "KEYPRESS") -> dict:
        """Send raw key command by codeset and code."""
        resp = await self._client.put(
            "/key_command/",
            headers=self._headers,
            json={
                "KEYLIST": [{
                    "CODESET": codeset,
                    "CODE": code,
                    "ACTION": action,
                }]
            }
        )
        return resp.json()

    # ============ Volume ============

    async def volume_up(self, amount: int = 1) -> dict:
        """Increase volume."""
        result = None
        for _ in range(amount):
            result = await self.send_key("vol_up")
        return result

    async def volume_down(self, amount: int = 1) -> dict:
        """Decrease volume."""
        result = None
        for _ in range(amount):
            result = await self.send_key("vol_down")
        return result

    async def mute_toggle(self) -> dict:
        return await self.send_key("mute_toggle")

    async def mute_on(self) -> dict:
        return await self.send_key("mute_on")

    async def mute_off(self) -> dict:
        return await self.send_key("mute_off")

    # ============ Settings ============

    async def get_settings(self, category: str) -> dict:
        """Get settings for a category (picture, audio, etc.)."""
        resp = await self._client.get(
            f"/menu_native/dynamic/tv_settings/{category}",
            headers=self._headers,
            params={"FLAT": "TRUE", "HELPTEXT": "FALSE", "HASHONLY": "FALSE"}
        )
        return resp.json()

    async def set_setting(self, category: str, setting: str, value: Any, hashval: int) -> dict:
        """Set a specific setting value."""
        resp = await self._client.put(
            f"/menu_native/dynamic/tv_settings/{category}/{setting}",
            headers=self._headers,
            json={
                "REQUEST": "MODIFY",
                "VALUE": value,
                "HASHVAL": hashval,
            }
        )
        return resp.json()

    async def get_picture_settings(self) -> dict:
        """Get all picture settings."""
        return await self.get_settings("picture")

    async def get_audio_settings(self) -> dict:
        """Get all audio settings."""
        return await self.get_settings("audio")

    async def _get_setting_hashval(self, category: str, cname: str) -> int | None:
        """Get the current hashval for a setting."""
        settings = await self.get_settings(category)
        for item in settings.get("ITEMS", []):
            if item.get("CNAME") == cname:
                return item.get("HASHVAL")
        return None

    async def set_picture_setting(self, cname: str, value: Any) -> dict:
        """Set any picture setting by cname, fetching hashval dynamically."""
        hashval = await self._get_setting_hashval("picture", cname)
        if hashval is None:
            return {"STATUS": {"RESULT": "FAILURE", "DETAIL": f"Setting {cname} not found"}}
        return await self.set_setting("picture", cname, value, hashval)

    async def set_backlight(self, value: int) -> dict:
        """Set backlight level (0-100)."""
        value = max(0, min(100, value))
        return await self.set_picture_setting("backlight", value)

    async def set_brightness(self, value: int) -> dict:
        """Set brightness level (0-100)."""
        value = max(0, min(100, value))
        return await self.set_picture_setting("brightness", value)

    async def set_contrast(self, value: int) -> dict:
        """Set contrast level (0-100)."""
        value = max(0, min(100, value))
        return await self.set_picture_setting("contrast", value)

    async def set_picture_mode(self, mode: str) -> dict:
        """Set picture mode (Vivid, Bright, Calibrated, Calibrated Dark, Game, Sports)."""
        return await self.set_picture_setting("picture_mode", mode)

    # ============ Inputs ============

    async def get_inputs(self) -> dict:
        """Get list of available inputs."""
        resp = await self._client.get(
            "/menu_native/dynamic/tv_settings/devices/name_input",
            headers=self._headers,
        )
        return resp.json()

    async def get_current_input(self) -> dict:
        """Get current input."""
        resp = await self._client.get(
            "/menu_native/dynamic/tv_settings/devices/current_input",
            headers=self._headers,
        )
        return resp.json()

    async def set_input(self, input_name: str, hashval: int) -> dict:
        """Set input by name (e.g., 'HDMI-1', 'SMARTCAST')."""
        # Get current input hashval for the MODIFY request
        current = await self.get_current_input()
        current_hashval = current.get("ITEMS", [{}])[0].get("HASHVAL", hashval)

        resp = await self._client.put(
            "/menu_native/dynamic/tv_settings/devices/current_input",
            headers=self._headers,
            json={
                "REQUEST": "MODIFY",
                "VALUE": input_name,
                "HASHVAL": current_hashval,
            }
        )
        return resp.json()

    async def cycle_input(self) -> dict:
        """Cycle to next input."""
        return await self.send_key("input_cycle")

    # ============ Navigation ============

    async def nav_up(self) -> dict:
        return await self.send_key("up")

    async def nav_down(self) -> dict:
        return await self.send_key("down")

    async def nav_left(self) -> dict:
        return await self.send_key("left")

    async def nav_right(self) -> dict:
        return await self.send_key("right")

    async def nav_ok(self) -> dict:
        return await self.send_key("ok")

    async def nav_back(self) -> dict:
        return await self.send_key("back")

    async def nav_home(self) -> dict:
        return await self.send_key("home")

    async def nav_menu(self) -> dict:
        return await self.send_key("menu")

    async def nav_exit(self) -> dict:
        return await self.send_key("exit")

    # ============ Media ============

    async def media_play(self) -> dict:
        return await self.send_key("play")

    async def media_pause(self) -> dict:
        return await self.send_key("pause")

    async def media_stop(self) -> dict:
        return await self.send_key("stop")

    async def media_rewind(self) -> dict:
        return await self.send_key("rew")

    async def media_fast_forward(self) -> dict:
        return await self.send_key("ff")

    async def media_prev(self) -> dict:
        return await self.send_key("prev")

    async def media_next(self) -> dict:
        return await self.send_key("next")

"""Yunatt 门禁 Home Assistant 集成.

设备: TM-AI07F (AiFace)
协议: WebSocket JSON, port 7792, path /pub/chat
事件: cmd=sendlog → HA event yunatt_access
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN, SIGNAL_ACCESS_EVENT, SIGNAL_DOOR_OPEN,
    SIGNAL_ONLINE, CONF_PORT, OFFLINE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    port = entry.data.get(CONF_PORT, 7792)
    server = YunattServer(hass, port)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = server
    await server.start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    server = hass.data[DOMAIN].pop(entry.entry_id)
    await server.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class YunattServer:
    """WebSocket 服务器，接收门禁设备事件."""

    def __init__(self, hass: HomeAssistant, port: int) -> None:
        self.hass = hass
        self.port = port
        self._server = None
        self.device_info: dict = {}
        self.last_event: dict | None = None
        self.online: bool = False
        self._offline_handle = None

    async def start(self) -> None:
        try:
            import websockets
        except ImportError:
            _LOGGER.error("请安装 websockets: pip install websockets")
            return

        self._server = await websockets.serve(
            self._handle_device, "0.0.0.0", self.port
        )
        _LOGGER.info("Yunatt WebSocket 服务器已启动 port=%d", self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def _set_online(self, online: bool) -> None:
        if self.online != online:
            self.online = online
            async_dispatcher_send(self.hass, SIGNAL_ONLINE, online)
            _LOGGER.info("设备%s", "上线" if online else "离线")

    def _reset_offline_timer(self) -> None:
        if self._offline_handle:
            self._offline_handle.cancel()
        self._offline_handle = self.hass.loop.call_later(
            OFFLINE_TIMEOUT, lambda: self._set_online(False)
        )

    async def _handle_device(self, websocket) -> None:
        addr = websocket.remote_address
        _LOGGER.info("设备连接: %s", addr)
        self._set_online(True)
        self._reset_offline_timer()
        try:
            async for raw in websocket:
                self._reset_offline_timer()
                if isinstance(raw, bytes):
                    try:
                        raw = raw.decode("utf-8")
                    except Exception:
                        continue
                try:
                    data = json.loads(raw)
                except Exception:
                    continue

                cmd = data.get("cmd") or data.get("ret", "")
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await self._dispatch(websocket, cmd, data, now)

        except Exception as e:
            _LOGGER.debug("设备断开 %s: %s", addr, e)

    async def _dispatch(self, ws, cmd: str, data: dict, now: str) -> None:
        if cmd == "reg":
            self.device_info = {
                "sn": data.get("sn"),
                "mac": data.get("mac"),
                "devinfo": data.get("devinfo", {}),
            }
            ack = {"ret": "reg", "result": True, "cloudtime": now}
            await ws.send(json.dumps(ack))
            _LOGGER.debug("设备注册: sn=%s", data.get("sn"))

        elif cmd == "heartbeat":
            ack = {"ret": "heartbeat", "result": True, "cloudtime": now}
            await ws.send(json.dumps(ack))

        elif cmd == "sendlog":
            logindex = data.get("logindex", 0)
            for record in data.get("record", []):
                event_data = {
                    "sn": data.get("sn"),
                    "name": record.get("name", ""),
                    "enrollid": record.get("enrollid"),
                    "mode": record.get("mode"),
                    "mode_name": _mode_name(record.get("mode")),
                    "inout": record.get("inout"),
                    "event": record.get("event"),
                    "time": record.get("time"),
                    "aliasid": record.get("aliasid", ""),
                }
                self.last_event = event_data
                _LOGGER.info(
                    "门禁事件: name=%s mode=%s time=%s",
                    event_data["name"], event_data["mode_name"], event_data["time"]
                )
                # 触发 HA 事件
                self.hass.bus.async_fire(f"{DOMAIN}_access", event_data)
                # 触发 sensor / binary_sensor 更新
                async_dispatcher_send(self.hass, SIGNAL_ACCESS_EVENT, event_data)
                async_dispatcher_send(self.hass, SIGNAL_DOOR_OPEN, True)

            ack = {"ret": "sendlog", "result": True, "logindex": logindex}
            await ws.send(json.dumps(ack))

        else:
            # 未知命令——记录完整内容，尝试作为事件派发
            _LOGGER.info("未知命令 cmd=%s data=%s", cmd, data)
            # 若含 record 字段（可能是不同命名的日志命令），同样派发事件
            for record in data.get("record", []):
                event_data = {
                    "sn": data.get("sn"),
                    "name": record.get("name", ""),
                    "enrollid": record.get("enrollid"),
                    "mode": record.get("mode"),
                    "mode_name": _mode_name(record.get("mode")),
                    "inout": record.get("inout"),
                    "event": record.get("event"),
                    "time": record.get("time"),
                    "aliasid": record.get("aliasid", ""),
                    "cmd": cmd,
                }
                self.last_event = event_data
                _LOGGER.info("门禁事件(未知cmd): name=%s mode=%s", event_data["name"], event_data["mode_name"])
                self.hass.bus.async_fire(f"{DOMAIN}_access", event_data)
                async_dispatcher_send(self.hass, SIGNAL_ACCESS_EVENT, event_data)
            ack = {"ret": cmd, "result": True, "cloudtime": now}
            await ws.send(json.dumps(ack))


def _mode_name(mode: int | None) -> str:
    modes = {
        1: "fingerprint",
        4: "card",
        8: "face",
        128: "password",
    }
    return modes.get(mode, f"unknown({mode})")

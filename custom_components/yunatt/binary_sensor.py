"""Yunatt 二进制传感器: 门打开 + 设备在线."""
from __future__ import annotations
import asyncio

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_DOOR_OPEN, SIGNAL_ONLINE, DOOR_OPEN_SECONDS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    server = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        YunattDoorSensor(entry),
        YunattOnlineSensor(server, entry),
    ])


class YunattDoorSensor(BinarySensorEntity):
    """收到刷脸/刷卡后短暂亮起，DOOR_OPEN_SECONDS 秒后自动复位."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_has_entity_name = True
    _attr_name = "Door"
    _attr_is_on = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_door"
        self._reset_task: asyncio.Task | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_DOOR_OPEN, self._on_door_open)
        )

    @callback
    def _on_door_open(self, _: bool) -> None:
        if self._reset_task:
            self._reset_task.cancel()
        self._attr_is_on = True
        self.async_write_ha_state()
        self._reset_task = self.hass.async_create_task(self._auto_reset())

    async def _auto_reset(self) -> None:
        await asyncio.sleep(DOOR_OPEN_SECONDS)
        self._attr_is_on = False
        self.async_write_ha_state()


class YunattOnlineSensor(BinarySensorEntity):
    """设备在线状态：有 WebSocket 连接且 3 分钟内有心跳."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Online"

    def __init__(self, server, entry: ConfigEntry) -> None:
        self._server = server
        self._attr_unique_id = f"{entry.entry_id}_online"

    @property
    def is_on(self) -> bool:
        return self._server.online

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_ONLINE, self._on_online_change)
        )

    @callback
    def _on_online_change(self, online: bool) -> None:
        self.async_write_ha_state()

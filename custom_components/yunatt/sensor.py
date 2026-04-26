"""Yunatt 门禁传感器 — 显示最近一次刷卡/刷脸记录."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_ACCESS_EVENT


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    server = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YunattLastAccessSensor(server, entry)])


class YunattLastAccessSensor(SensorEntity):
    """最近一次门禁事件传感器."""

    _attr_has_entity_name = True
    _attr_name = "Last Access"
    _attr_icon = "mdi:door"

    def __init__(self, server, entry: ConfigEntry) -> None:
        self._server = server
        self._attr_unique_id = f"{entry.entry_id}_last_access"
        self._event: dict | None = None

    @property
    def native_value(self) -> str | None:
        if self._event:
            return self._event.get("name", "unknown")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        if not self._event:
            return {}
        return {
            "enrollid": self._event.get("enrollid"),
            "mode": self._event.get("mode_name"),
            "time": self._event.get("time"),
            "inout": self._event.get("inout"),
            "sn": self._event.get("sn"),
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ACCESS_EVENT, self._handle_event
            )
        )

    @callback
    def _handle_event(self, event: dict) -> None:
        self._event = event
        self.async_write_ha_state()

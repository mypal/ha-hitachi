import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import UnitOfTemperature, STATE_UNAVAILABLE

from . import HitachiConfigEntry
from .coordinator import Coordinator
from .const import SwitchEnum, KEY_NAME, KEY_CODE, KEY_MAC, KEY_MODE, KEY_STATE, ModeEnum

from .const import DOMAIN, CONF_REFRESH_TOKEN
from .request import refresh_auth, req_homes, req_status


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: HitachiConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry example."""
    # assuming API object stored here by __init__.py
    _LOGGER.debug('switch async_setup_entry')
    coordinator = entry.runtime_data.coordinator

    devices = coordinator.get_devices()
    entities = []
    _LOGGER.debug(devices)
    home_ids = list(devices.keys())
    for home_id in home_ids:
        xkq_devices = devices[home_id]['xkqList']
        xkq_list = [HitachiSwitch(home_id, xkq[KEY_CODE], switch_enum, coordinator) for xkq in xkq_devices for switch_enum in SwitchEnum]
        _LOGGER.debug(f"home_id: {home_id} has {len(xkq_list)}")
        entities += xkq_list

    _LOGGER.debug(f"add entities: {len(entities)}")
    async_add_entities(
        entities
    )

UNIQUE_ID_PREFIX = 'hitachi_'

class HitachiSwitch(CoordinatorEntity[Coordinator], SwitchEntity):
    """Representation of a HitachiSwitch."""

    def __init__(self, home_id: str, xkq_code: str, key: SwitchEnum, coordinator: Coordinator):
        """Initialize the switch."""
        super().__init__(coordinator)

        self._coordinator = coordinator
        self._home_id = home_id
        self._xkq_code = xkq_code
        self._key = key

        self._attr_device_class = SwitchDeviceClass.SWITCH

        dev = self._coordinator.get_data(
            self._home_id, self._xkq_code
        )
        if dev:
            name_suffix = ''
            if self._key == SwitchEnum.switch:
                name_suffix = '开关'
            elif self._key == SwitchEnum.eco:
                name_suffix = '节能模式'
            elif self._key == SwitchEnum.silent:
                name_suffix = '静音模式'
            elif self._key == SwitchEnum.dryfloor:
                name_suffix = '地板干燥模式'
            elif self._key == SwitchEnum.lock:
                name_suffix = '童锁'
            # elif self._key == SwitchEnum.keytone:
            #     name_suffix = '按键音'
            # elif self._key == SwitchEnum.led:
            #     name_suffix = '开关指示灯'
            self._attr_name = dev[KEY_NAME]+name_suffix
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"hitachi_{dev[KEY_MAC]}")},
                name=dev[KEY_NAME],
                manufacturer="Hitachi, Ltd.",
                model='xkq',
            )

            self._attr_unique_id = f"hitachi-{dev[KEY_MAC]}-{key.name}"

        self._update_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self):
        dev = self._coordinator.get_data(
            self._home_id, self._xkq_code
        )
        if dev:
            available = True
            if self._key == SwitchEnum.eco or self._key == SwitchEnum.silent:
                available = dev[KEY_STATE] != 0
            elif self._key == SwitchEnum.dryfloor:
                available = dev[KEY_STATE] != 0 and dev[KEY_MODE] == ModeEnum.FLOOR_HEAT.value
            if available != self._attr_available:
                self._attr_available = available

            if available:
                self._attr_is_on = dev[self._key.value] == 1

    @property
    def available(self):
        return self._attr_available

    async def _async_control(self, value):
        _LOGGER.debug('control')
        res = await self._coordinator.control(self._home_id, self._xkq_code, {
            self._key.value: value,
        })
        _LOGGER.debug(res)
        await self._coordinator.async_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_control(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_control(0)

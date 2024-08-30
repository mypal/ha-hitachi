import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE, PRECISION_WHOLE, PRECISION_HALVES

from . import HitachiConfigEntry
from .coordinator import Coordinator
from .const import (
    KEY_NAME, KEY_CODE, KEY_MAC, 
    KEY_STATE, KEY_MODE, 
    KEY_TARGET_TEMP, KEY_CUR_TEMP, KEY_COLD_MIN, KEY_COLD_MAX, KEY_HEAT_MIN, KEY_HEAT_MAX,
    ModeEnum
)

from .const import DOMAIN, CONF_REFRESH_TOKEN
from .request import refresh_auth, req_homes, req_status


_LOGGER = logging.getLogger(__name__)

def _get_mode(state: int, mode: int | None = None) -> HVACMode:
    if state == 0:
        return HVACMode.OFF
    if mode == ModeEnum.COLD.value:
        return HVACMode.COOL
    if mode == ModeEnum.HEAT.value:
        return HVACMode.HEAT
    if mode == ModeEnum.FLOOR_HEAT.value:
        return HVACMode.DRY

def _gen_payload(mode: HVACMode) -> dict:
    if mode == HVACMode.OFF:
        return {
            KEY_STATE: 0,
        }
    if mode == HVACMode.COOL:
        return {
            KEY_STATE: 1,
            KEY_MODE: ModeEnum.COLD.value,
        }
    if mode == HVACMode.HEAT:
        return {
            KEY_STATE: 1,
            KEY_MODE: ModeEnum.HEAT.value
        }
    if mode == HVACMode.DRY:
        return {
            KEY_STATE: 1,
            KEY_MODE: ModeEnum.FLOOR_HEAT.value
        }

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: HitachiConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry example."""
    # assuming API object stored here by __init__.py
    _LOGGER.debug('climate async_setup_entry')
    coordinator = entry.runtime_data.coordinator

    devices = coordinator.get_devices()
    entities = []
    _LOGGER.debug(devices)
    home_ids = list(devices.keys())
    for home_id in home_ids:
        xkq_devices = devices[home_id]['xkqList']
        xkq_list = [HitachiClimate(home_id, xkq[KEY_CODE], coordinator) for xkq in xkq_devices]
        _LOGGER.debug(f"home_id: {home_id} has {len(xkq_list)}")
        entities += xkq_list

    _LOGGER.debug(f"add entities: {len(entities)}")
    async_add_entities(
        entities
    )

UNIQUE_ID_PREFIX = 'hitachi_'

class HitachiClimate(CoordinatorEntity[Coordinator], ClimateEntity):
    """Representation of a HitachiClimate."""

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator):
        """Initialize the climate."""
        super().__init__(coordinator)

        self._coordinator = coordinator
        self._home_id = home_id
        self._xkq_code = xkq_code

        dev = self._coordinator.get_data(
            self._home_id, self._xkq_code
        )
        if dev:
            self._attr_name = dev[KEY_NAME]
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"hitachi_{dev[KEY_MAC]}")},
                name=dev[KEY_NAME],
                manufacturer="Hitachi, Ltd.",
                model='xkq',
            )

            self._attr_unique_id = f"hitachi-{dev[KEY_MAC]}"

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_OFF |
            ClimateEntityFeature.TURN_ON
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY]
        self._attr_target_temperature_step = PRECISION_HALVES
        self._attr_precision = PRECISION_WHOLE

        self._update_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        payload = {}
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
            payload[KEY_TARGET_TEMP] = kwargs.get(ATTR_TEMPERATURE)
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._attr_hvac_mode = hvac_mode
            payload.update(_gen_payload(hvac_mode))

        res = await self._coordinator.control(self._home_id, self._xkq_code, payload)
        _LOGGER.debug(res)
        await self._coordinator.async_refresh()


    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        res = await self._coordinator.control(self._home_id, self._xkq_code, _gen_payload(hvac_mode))
        _LOGGER.debug(res)
        await self._coordinator.async_refresh()
    
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        _LOGGER.debug('turn on')
        dev = self._coordinator.get_data(
            self._home_id, self._xkq_code
        )
        if dev:
            mode = _get_mode(1, dev[KEY_MODE])
            await self.async_set_hvac_mode(mode)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        _LOGGER.debug('turn off')
        await self.async_set_hvac_mode(_get_mode(0))

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
            self._attr_target_temperature = dev[KEY_TARGET_TEMP]
            self._attr_current_temperature = dev[KEY_CUR_TEMP]
            self._attr_hvac_mode = _get_mode(dev[KEY_STATE], dev[KEY_MODE])
            if dev[KEY_MODE] == ModeEnum.COLD:
                self._attr_min_temp = dev[KEY_COLD_MIN]
                self._attr_max_temp = dev[KEY_COLD_MAX]
            else:
                self._attr_min_temp = dev[KEY_HEAT_MIN]
                self._attr_max_temp = dev[KEY_HEAT_MAX]

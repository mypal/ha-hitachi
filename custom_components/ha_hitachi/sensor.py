import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.const import UnitOfTemperature

from . import HitachiConfigEntry
from .coordinator import Coordinator
from .const import SensorEnum, KEY_NAME, KEY_CODE, KEY_MAC

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
    _LOGGER.debug('sensor async_setup_entry')
    coordinator = entry.runtime_data.coordinator

    devices = coordinator.get_devices()
    entities = []
    _LOGGER.debug(devices)
    home_ids = list(devices.keys())
    for home_id in home_ids:
        xkq_devices = devices[home_id]['xkqList']
        xkq_list = [HitachiSensor(home_id, xkq[KEY_CODE], sensor_enum, coordinator) for xkq in xkq_devices for sensor_enum in SensorEnum]
        _LOGGER.debug(f"home_id: {home_id} has {len(xkq_list)}")
        entities += xkq_list

    _LOGGER.debug(f"add entities: {len(entities)}")
    async_add_entities(
        entities
    )

UNIQUE_ID_PREFIX = 'hitachi_'

class HitachiSensor(CoordinatorEntity[Coordinator], SensorEntity):
    """Representation of a HitachiSensor."""

    def __init__(self, home_id: str, xkq_code: str, key: SensorEnum, coordinator: Coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._coordinator = coordinator
        self._home_id = home_id
        self._xkq_code = xkq_code
        self._key = key

        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        # self._attr_native_value = state
        self._attr_state_class = SensorStateClass.MEASUREMENT

        dev = self._coordinator.get_data(
            self._home_id, self._xkq_code
        )
        if dev:
            name_suffix = ''
            if self._key == SensorEnum.target:
                name_suffix = '设置温度'
            elif self._key == SensorEnum.inlet:
                name_suffix = '回水温度'
            elif self._key == SensorEnum.outlet:
                name_suffix = '出水温度'
            elif self._key == SensorEnum.current:
                name_suffix = '环境温度'
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
            self._attr_native_value = dev[self._key.value]

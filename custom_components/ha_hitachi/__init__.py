"""init"""

import logging
from dataclasses import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_REFRESH_TOKEN
# from .hit_ctrl import HitCtrl
from .coordinator import Coordinator


PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.CLIMATE]

@dataclass
class HitachiData:
    coordinator: Coordinator


type HitachiConfigEntry = ConfigEntry[HitachiData]


_LOGGER = logging.getLogger(__name__)

def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)

async def async_setup_entry(
        hass: HomeAssistant, entry: HitachiConfigEntry
):
    hass.data.setdefault(DOMAIN, {})
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    token = entry.data[CONF_TOKEN]
    refresh_token = entry.data[CONF_REFRESH_TOKEN]

    coordinator = Coordinator(hass, username, password, token, refresh_token)
    entry.runtime_data = HitachiData(coordinator=coordinator)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug('async_setup_entry finished')
    return True

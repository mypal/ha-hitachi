"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta, datetime
import logging
import asyncio
import async_timeout

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN, CONF_REFRESH_TOKEN, KEY_CODE, KEY_NAME, KEY_HEAT_MAX, KEY_HEAT_MIN, 
    KEY_COLD_MAX, KEY_COLD_MIN, KEY_MAC, KEY_HOME_ID, KEY_STATE, KEY_TARGET_TEMP, 
    KEY_MODE, KEY_ECO, KEY_SILENT, KEY_DRY_FLOOR, KEY_LOCK, KEY_OUTLET_TEMP, 
    KEY_INLET_TEMP, KEY_CUR_TEMP, KEY_TS, KEY_XKQ_TYPE, KEY_DEVICE_TYPE, KEY_KEY_TONE,
    KEY_LED_BRIGHT, KEY_SCREEN_BRIGHT
)
from .request import refresh_auth, req_homes, req_status, req_cmd, set_hass


_LOGGER = logging.getLogger(__name__)

INTERVAL = timedelta(seconds=10)

class Coordinator(DataUpdateCoordinator[dict]):
    """My custom coordinator."""

    def __init__(self, hass, username, password, token, refresh_token):
        """Initialize my coordinator."""
        _LOGGER.debug('Coordinator.init')
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Hitachi",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=INTERVAL,
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True
        )
        self._hass = hass
        self._username = username
        self._password = password
        self._token = token
        self._refresh_token = refresh_token
        self._devices = {}
        self._ts = datetime.now()
        set_hass(hass)

    async def _async_setup(self):
        """Set up the coordinator

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        _LOGGER.debug('Coordinator._async_setup')
        res = await self._auth()
        if not res:
            _LOGGER.debug('auth failed')
            raise ConfigEntryAuthFailed

        for home in res['data']['homeList']:
            home_id = home[KEY_HOME_ID]
            home_data = await req_homes(home[KEY_HOME_ID])
            self._devices[home_id] = {
                'xkqList': [{
                    KEY_TS: 0,
                    KEY_CODE: xkq[KEY_CODE],
                    KEY_NAME: xkq[KEY_NAME],
                    KEY_HEAT_MAX: xkq[KEY_HEAT_MAX],
                    KEY_HEAT_MIN: xkq[KEY_HEAT_MIN],
                    KEY_MAC: xkq[KEY_MAC],
                    KEY_COLD_MAX: xkq[KEY_COLD_MAX],
                    KEY_COLD_MIN: xkq[KEY_COLD_MIN],
                    KEY_HOME_ID: home_id,
                    KEY_DEVICE_TYPE: xkq['type'],
                    KEY_XKQ_TYPE: xkq[KEY_XKQ_TYPE],
                } for xkq in home_data['data']['homeDetail']['xkqList']],
            }
        _LOGGER.debug('devices:')
        _LOGGER.debug(self._devices)

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        _LOGGER.debug('Coordinator._async_update_data')
        await self._refresh_auth()
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                devices = self._devices
                home_ids = list(devices.keys())
                for home_id in home_ids:
                    xkq_devices = devices[home_id]['xkqList']
                    xkq_list = [{
                        KEY_TS: 0, # xkq[KEY_TS]
                        KEY_CODE: xkq[KEY_CODE]
                    } for xkq in xkq_devices]
                    res = await req_status(home_id, xkq_list)
                    xkq_status = res['data']['xkqStatusList']
                    for xkq in xkq_devices:
                        status = [item for item in xkq_status if item.get(KEY_CODE) == xkq[KEY_CODE]][0]
                        xkq[KEY_STATE] = status[KEY_STATE]
                        xkq[KEY_TARGET_TEMP] = status[KEY_TARGET_TEMP]
                        xkq[KEY_MODE] = status[KEY_MODE]
                        xkq[KEY_ECO] = status[KEY_ECO]
                        xkq[KEY_SILENT] = status[KEY_SILENT]
                        xkq[KEY_DRY_FLOOR] = status[KEY_DRY_FLOOR]
                        xkq[KEY_LOCK] = status[KEY_LOCK]
                        xkq[KEY_OUTLET_TEMP] = status[KEY_OUTLET_TEMP]
                        xkq[KEY_INLET_TEMP] = status[KEY_INLET_TEMP]
                        xkq[KEY_CUR_TEMP] = status[KEY_CUR_TEMP]
                        xkq[KEY_KEY_TONE] = status[KEY_KEY_TONE]
                        xkq[KEY_LED_BRIGHT] = status[KEY_LED_BRIGHT]
                        xkq[KEY_SCREEN_BRIGHT] = status[KEY_SCREEN_BRIGHT]
                _LOGGER.debug(self._devices)
                return self._devices
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    async def _auth(self):
        username = self._username
        password = self._password
        token = self._token
        refresh_token = self._refresh_token
        hass = self._hass

        par = await refresh_auth(username, password, token, refresh_token)
        if (not par):
            _LOGGER.debug('auth failed')
            return False

        token, refresh_token, res = par

        hass.data[DOMAIN][CONF_USERNAME] = username
        hass.data[DOMAIN][CONF_PASSWORD] = password
        hass.data[DOMAIN][CONF_TOKEN] = token
        hass.data[DOMAIN][CONF_REFRESH_TOKEN] = refresh_token
        self._token = token
        self._refresh_token = refresh_token
        _LOGGER.debug('auth success')
        return res
    
    def get_data(self, home_id: str, xkq_code: str):
        devices = self._devices
        dev = [item for item in devices[home_id]['xkqList'] if item[KEY_CODE] == xkq_code]
        if len(dev) > 0:
            return dev[0]
        return None

    async def control(self, home_id, xkq_code, cmd_dict):
        dev = self.get_data(home_id, xkq_code)
        device_info = {
            KEY_HOME_ID: home_id,
            KEY_CODE: xkq_code,
            KEY_DEVICE_TYPE: dev[KEY_DEVICE_TYPE],
            KEY_XKQ_TYPE: dev[KEY_XKQ_TYPE],
        }
        return await req_cmd(device_info, cmd_dict)

    def get_devices(self):
        return self._devices

    async def _refresh_auth(self):
        now = datetime.now()
        if now - self._ts > timedelta(days=1):
            self._ts = now
            try:
                _LOGGER.debug('refresh auth')
                await self._auth()
            except Exception:
                _LOGGER.error('auth poll failed')
                _LOGGER.exception(Exception)

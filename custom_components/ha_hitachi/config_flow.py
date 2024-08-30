from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_REFRESH_TOKEN
from .request import refresh_auth

_LOGGER = logging.getLogger(__name__)


def _log(s: str) -> object:
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


class HitachiHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.user_input = {}

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        _LOGGER.debug('async_step_user')
        if user_input is not None:
            self.user_input.update(user_input)
            _LOGGER.debug('Authing...')
            res = await refresh_auth(self.user_input[CONF_USERNAME], self.user_input[CONF_PASSWORD])
            _LOGGER.debug(res)
            if res is not None:
                self.user_input[CONF_TOKEN], self.user_input[CONF_REFRESH_TOKEN], _ = res
                return self.async_create_entry(title=self.user_input[CONF_USERNAME], data=self.user_input)
            else:
                errors = { 'base': 'invalid_login' }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }), errors=errors
        )

"""Config flow for Jablotron Cloud integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .jablotron import JablotronClient, UnexpectedResponse

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PIN, default=""): str,
    }
)


async def test_credentials(hass: HomeAssistant, data: dict) -> None:
    """Validate that user entered valid credentials."""

    # Initialize Jablotron client and validate entered credentials
    client = JablotronClient(data[CONF_USERNAME], data[CONF_PASSWORD])
    bridge = client.get_bridge()
    try:
        await hass.async_add_executor_job(bridge.get_session_id)
    except UnexpectedResponse as ex:
        raise InvalidAuth from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Jablotron Cloud."""

    VERSION = 2

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """User flow to configure Jablotron Cloud integration."""

        # Keep the form open if no user input is provided
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        # Validate user input and fail if credentials are invalid
        try:
            await test_credentials(self.hass, user_input)
        except InvalidAuth:
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error occurred during credentials validation!"
            )

            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "unknown"},
            )
        else:
            return self.async_create_entry(title="Jablotron Cloud", data=user_input)


class InvalidAuth(HomeAssistantError):
    """Error to indicate that user entered invalid credentials."""

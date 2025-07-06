"""Client for Jablotron Cloud API."""

import logging

from homeassistant.helpers.update_coordinator import UpdateFailed
from jablotronpy import Jablotron, UnexpectedResponse

_LOGGER = logging.getLogger(__name__)


class JablotronClient:
    """Client for Jablotron Cloud API."""

    def __init__(self, username: str, password: str, default_pin: str = "") -> None:
        """Initialize Jablotron client."""

        self._username = username
        self._password = password
        self._default_pin = default_pin

    def get_bridge(self, pin: str = "") -> Jablotron:
        """Return Jablotron bridge instance."""

        bridge = Jablotron(self._username, self._password, pin)
        bridge.set_cookies()

        return bridge

    def get_services(self, bridge: Jablotron) -> list[dict]:
        """Return services from Jablotron Cloud."""

        try:
            return bridge.get_services()
        except UnexpectedResponse as error:
            _LOGGER.error("Failed to get services from Jablotron!")
            raise UpdateFailed("Failed to get services from Jablotron!") from error

    def get_gates(
        self, bridge: Jablotron, service_id: int, service_type: str
    ) -> list[dict]:
        """Return gates for service from Jablotron Cloud."""

        try:
            return bridge.get_programmable_gates(service_id, service_type)
        except UnexpectedResponse as error:
            _LOGGER.error(
                "Failed to get gates for service '%d' from Jablotron!", service_id
            )
            raise UpdateFailed(
                f"Failed to get gates for service '{service_id}' from Jablotron!"
            ) from error

    def get_sections(
        self, bridge: Jablotron, service_id: int, service_type: str
    ) -> list[dict]:
        """Return sections for service from Jablotron Cloud."""

        try:
            return bridge.get_sections(service_id, service_type)
        except UnexpectedResponse as error:
            _LOGGER.error(
                "Failed to get sections for service '%d' from Jablotron!", service_id
            )
            raise UpdateFailed(
                f"Failed to get sections for service '{service_id}' from Jablotron!"
            ) from error

    def get_thermo_devices(
        self, bridge: Jablotron, service_id: int, service_type: str
    ) -> list[dict]:
        """Return thermo devices for service from Jablotron Cloud."""

        try:
            return bridge.get_thermo_devices(service_id, service_type)
        except UnexpectedResponse as error:
            _LOGGER.error(
                "Failed to get thermo devices for service '%d' from Jablotron!",
                service_id,
            )
            raise UpdateFailed(
                f"Failed to get thermo devices for service '{service_id}' from Jablotron!"
            ) from error

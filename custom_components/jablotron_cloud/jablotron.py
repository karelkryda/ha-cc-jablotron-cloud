"""Client for Jablotron Cloud API."""

from jablotronpy import Jablotron


class JablotronClient:
    """Client for Jablotron Cloud API."""

    def __init__(self, username: str, password: str, default_pin: str | None = None) -> None:
        """Initialize Jablotron client."""

        self._username = username
        self._password = password
        self._default_pin = default_pin

    @property
    def default_pin(self):
        """Return default pin for Jablotron Cloud API."""

        return self._default_pin

    def get_bridge(self) -> Jablotron:
        """Return Jablotron bridge instance."""

        bridge = Jablotron(self._username, self._password, self._default_pin)
        bridge.perform_login()

        return bridge

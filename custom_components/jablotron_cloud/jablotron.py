"""Client for Jablotron Cloud API."""

from jablotronpy import Jablotron


class JablotronClient:
    """Client for Jablotron Cloud API."""

    def __init__(self, username: str, password: str, default_pin: str | None = None, force_arm: bool = True) -> None:
        """Initialize Jablotron client."""

        self._username = username
        self._password = password
        self._default_pin = default_pin
        self._force_arm = force_arm

    @property
    def force_arm(self):
        """Return whether arm should be forced."""

        return self._force_arm

    def get_bridge(self) -> Jablotron:
        """Return Jablotron bridge instance."""

        bridge = Jablotron(self._username, self._password, self._default_pin)
        bridge.perform_login()

        return bridge

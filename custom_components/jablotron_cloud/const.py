"""Constants for Jablotron Cloud integration."""
from enum import StrEnum

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import Platform

# Integration constants
DOMAIN = "jablotron_cloud"
UNSUPPORTED_SERVICES = ["FUTURA2", "AMBIENTA", "VOLTA", "LOGBOOK"]
PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SENSOR,
]

# API constants
SERVICE_TYPE = "service-type"
COMP_ID = "cloud-component-id"
DEVICE_ID = "object-device-id"


# Alarm control panel constants
class Actions(StrEnum):
    """Actions to control sections."""

    ARM = "ARM"
    DISARM = "DISARM"
    PARTIAL_ARM = "PARTIAL_ARM"


STATE_AS_ALARM_STATE = {
    Actions.ARM: AlarmControlPanelState.ARMED_AWAY,
    Actions.PARTIAL_ARM: AlarmControlPanelState.ARMED_HOME,
    Actions.DISARM: AlarmControlPanelState.DISARMED,
}

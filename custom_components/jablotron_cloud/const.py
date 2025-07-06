"""Constants for Jablotron Cloud integration."""

from enum import StrEnum

from homeassistant.const import Platform

# Integration constants
DOMAIN = "jablotron_cloud"
SERVICES_WITHOUT_PG = ["FUTURA2", "AMBIENTA", "VOLTA", "LOGBOOK"]
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

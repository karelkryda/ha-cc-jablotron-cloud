"""The Jablotron Cloud integration."""

from __future__ import annotations

import logging
from asyncio import timeout
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME, CONF_SCAN_INTERVAL, CONF_TIMEOUT, \
    CONF_FORCE_UPDATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PLATFORMS, SERVICE_TYPE, SERVICES_WITHOUT_PG
from .jablotron import JablotronClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jablotron Cloud from config entry."""

    _LOGGER.debug("Preparing Jablotron API client")
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    default_pin: str = entry.data[CONF_PIN]
    force_arm: bool = entry.data[CONF_FORCE_UPDATE]
    scan_interval: int = entry.data[CONF_SCAN_INTERVAL]
    scan_timeout: int = entry.data[CONF_TIMEOUT]
    client = JablotronClient(username, password, default_pin, force_arm)

    _LOGGER.debug("Preparing Jablotron data update coordinator")
    coordinator = JablotronDataCoordinator(hass, client, scan_interval, scan_timeout)

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle migration of config entry data."""

    # Get current config version
    version = config_entry.version
    minor_version = config_entry.minor_version

    # User has downgraded from a future version
    if version > 3:
        return False

    # Modify config entry based on previous version
    _LOGGER.debug("Migrating configuration from version %s.%s", version, minor_version)
    new_data = config_entry.data.copy()
    # Add default values for 'force_update', 'scan_interval' and 'timeout'
    if version == 2:
        new_data[CONF_FORCE_UPDATE] = True
        new_data[CONF_SCAN_INTERVAL] = 30
        new_data[CONF_TIMEOUT] = 30

    hass.config_entries.async_update_entry(config_entry, data=new_data, minor_version=1, version=3)
    _LOGGER.info("Migration to version %s.%s successful", config_entry.version, config_entry.minor_version)
    return True


class JablotronDataCoordinator(DataUpdateCoordinator):
    """Data coordinator around Jablotron Cloud API."""

    def __init__(self, hass: HomeAssistant, client: JablotronClient, scan_interval: int, scan_timeout: int) -> None:
        """Initialize Home Assistant data update coordinator."""

        # Define coordinator attributes
        self._client = client
        self._scan_interval = scan_interval
        self._scan_timeout = scan_timeout

        # Initialize data update coordinator
        super().__init__(
            hass,
            _LOGGER,
            name="Jablotron Cloud",
            update_interval=timedelta(seconds=scan_interval)
        )

    @property
    def client(self):
        """Return Jablotron Cloud client instance."""

        return self._client

    async def _async_update_data(self) -> dict:
        """Fetch data from Jablotron Cloud API."""

        async with timeout(self._scan_timeout):
            bridge = await self.hass.async_add_executor_job(self.client.get_bridge)

            # Get services from Jablotron Cloud
            services = await self.hass.async_add_executor_job(bridge.get_services)

            # Log that no services were discovered
            if not services:
                _LOGGER.warning(
                    "No services were discovered and therefore no entities will be generated!"
                )

            # Fetch data for each service
            data = {}
            for service in services:
                service_id: int = service["service-id"]
                service_type: str = service[SERVICE_TYPE]

                # Check whether service type is supported
                if service_type in SERVICES_WITHOUT_PG:
                    _LOGGER.debug(
                        "Service type '%s' is not supported, skipping update for service '%d'!",
                        service_type,
                        service_id
                    )

                    continue

                # Fetch gates for the service
                _LOGGER.debug("Updating data for service '%d'", service_id)
                gates = await self.hass.async_add_executor_job(bridge.get_programmable_gates, service_id, service_type)

                # Fetch sections for the service
                sections = await self.hass.async_add_executor_job(bridge.get_sections, service_id, service_type)

                # Fetch thermo devices for the service
                thermo_devices = await self.hass.async_add_executor_job(
                    bridge.get_thermo_devices, service_id, service_type
                )

                # Save fetched service data
                _LOGGER.debug("Data for service '%d' successfully updated.", service_id)
                data[service_id] = {
                    "service": service,
                    "gates": gates,
                    "sections": sections,
                    "thermo": thermo_devices,
                }

            return data

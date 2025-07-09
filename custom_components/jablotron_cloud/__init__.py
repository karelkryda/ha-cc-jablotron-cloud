"""The Jablotron Cloud integration."""

from __future__ import annotations

import logging
from asyncio import timeout
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME, CONF_SCAN_INTERVAL, CONF_TIMEOUT, \
    CONF_FORCE_UPDATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from jablotronpy import Jablotron, JablotronService

from .const import PLATFORMS, SERVICE_TYPE, UNSUPPORTED_SERVICES
from .jablotron import JablotronClient
from .types import JablotronServiceData

_LOGGER = logging.getLogger(__name__)

type JablotronConfigEntry = ConfigEntry[JablotronData]


async def async_setup_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:
    """Set up Jablotron Cloud from config entry."""

    _LOGGER.debug("Preparing Jablotron API client")
    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]
    default_pin: str = entry.data[CONF_PIN]
    force_arm: bool = entry.data[CONF_FORCE_UPDATE]
    client = JablotronClient(username, password, default_pin, force_arm)

    _LOGGER.debug("Preparing Jablotron data update coordinator")
    scan_interval: int = entry.data[CONF_SCAN_INTERVAL]
    scan_timeout: int = entry.data[CONF_TIMEOUT]
    coordinator = JablotronDataCoordinator(hass, client, scan_interval, scan_timeout)

    # Fetch initial data for platforms initialization
    await coordinator.async_config_entry_first_refresh()

    # Listen for configuration changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Prepare runtime data
    entry.runtime_data = JablotronData(client, coordinator)

    # Setup all supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: JablotronConfigEntry) -> bool:
    """Unload Jablotron Cloud integration."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: JablotronConfigEntry) -> None:
    """Handle configuration changes."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: JablotronConfigEntry) -> bool:
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
        new_data[CONF_TIMEOUT] = 15

    hass.config_entries.async_update_entry(config_entry, data=new_data, minor_version=1, version=3)
    _LOGGER.info("Migrated configuration to version %s.%s", config_entry.version, config_entry.minor_version)
    return True


@dataclass
class JablotronData:
    """Integration runtime data."""

    client: JablotronClient
    coordinator: JablotronDataCoordinator


class JablotronDataCoordinator(DataUpdateCoordinator):
    """Data coordinator for Jablotron Cloud integration."""

    def __init__(self, hass: HomeAssistant, client: JablotronClient, scan_interval: int, scan_timeout: int) -> None:
        """Initialize Home Assistant data update coordinator."""

        # Define coordinator attributes
        self.client = client
        self._scan_timeout = scan_timeout

        # Initialize data update coordinator
        super().__init__(
            hass,
            _LOGGER,
            name="Jablotron Cloud",
            update_interval=timedelta(seconds=scan_interval)
        )

    async def _async_setup(self) -> None:
        """Fetch initial data for all platforms."""

        # Get available services from Jablotron Cloud
        _LOGGER.debug("Discovering available Jablotron services")
        bridge: Jablotron = await self.hass.async_add_executor_job(self.client.get_bridge)
        services: list[JablotronService] = await self.hass.async_add_executor_job(bridge.get_services)

        # Log that no services were discovered
        if not services:
            _LOGGER.warning("No services were discovered and therefore no entities will be generated!")

        # Get all available platforms and their states for each service
        for service in services:
            # Get service details
            service_name = service["name"]
            service_id = service["service-id"]
            service_type = service["service-type"]

            # Check whether service type is supported
            if service_type in UNSUPPORTED_SERVICES:
                _LOGGER.debug("Service '%s' is not supported, ignoring!", service_type)

                continue

            # Initialize service data
            self.client.services[service_id] = JablotronServiceData(name=service_name, type=service_type)

            # Get available sections from Jablotron Cloud
            _LOGGER.debug("Discovering available sections for service '%d'", service_id)
            self.client.services[service_id]["alarm"] = await self.hass.async_add_executor_job(
                bridge.get_sections,
                service_id,
                service_type
            )

    #         # Fetch gates for the service
    #         _LOGGER.debug("Updating data for service '%d'", service_id)
    #         _LOGGER.warning("GET GATES")
    #         gates = await self.hass.async_add_executor_job(bridge.get_programmable_gates, service_id, service_type)
    #
    #         # Fetch thermo devices for the service
    #         _LOGGER.warning("GET THERMO DEVICES")
    #         thermo_devices = await self.hass.async_add_executor_job(
    #             bridge.get_thermo_devices, service_id, service_type
    #         )
    #
    #         # Save fetched service data
    #         _LOGGER.warning("DONE")
    #         _LOGGER.debug("Data for service '%d' successfully updated.", service_id)
    #         data[service_id] = {
    #             "service": service,
    #             "gates": gates,
    #             "sections": sections,
    #             "thermo": thermo_devices,
    #         }

    async def _async_update_data(self) -> dict:
        """Fetch data from Jablotron Cloud API."""

        _LOGGER.debug("Fetching data")
        return {}

        try:
            # async with timeout(1 if random.choice(range(3)) == 2 else self._scan_timeout):
            async with timeout(self._scan_timeout):
                # _LOGGER.warning("GET BRIDGE")
                bridge = await self.hass.async_add_executor_job(self.client.get_bridge)

                # Get services from Jablotron Cloud
                # _LOGGER.warning("GET SERVICES")
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
                    # _LOGGER.warning("GET GATES")
                    gates = await self.hass.async_add_executor_job(bridge.get_programmable_gates, service_id,
                                                                   service_type)

                    # Fetch sections for the service
                    # _LOGGER.warning("GET SECTIONS")
                    # sections = await self.hass.async_add_executor_job(bridge.get_sections, service_id, service_type)
                    sections = self.two if self.run < 5 else self.three
                    _LOGGER.warning(sections)

                    # Fetch thermo devices for the service
                    # _LOGGER.warning("GET THERMO DEVICES")
                    thermo_devices = await self.hass.async_add_executor_job(
                        bridge.get_thermo_devices, service_id, service_type
                    )

                    # Save fetched service data
                    # _LOGGER.warning("DONE")
                    _LOGGER.debug("Data for service '%d' successfully updated.", service_id)
                    data[service_id] = {
                        "service": service,
                        "gates": gates,
                        "sections": sections,
                        "thermo": thermo_devices,
                    }

                self.run = self.run + 1
                return data
        except Exception as err:
            _LOGGER.error("UPDATE ERROR: %s", err)
            raise UpdateFailed(err)
